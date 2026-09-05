import json
import logging
import os
import re
import secrets
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import aiohttp
from aiohttp import web

logging.basicConfig(level=logging.WARNING)
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)

DEMO_BACKEND = "demo"
STUDIO_BACKEND = "studio"
DEMO_BASE_URL = "https://qwen-qwen3-asr-demo.ms.show"
STUDIO_BASE_URL = "https://qwen-qwen3-asr.ms.show"

# Per-model token keys, e.g. `qwen3-asr-1-7b-studio-token=xxx`.
TOKEN_SUFFIX = "-studio-token"
TOKEN_RE = re.compile(r"^[A-Za-z0-9._~+/=-]+$")

USER_AGENT = "Mozilla/5.0 AppleWebKit/537.36 Chrome/143 Safari/537"
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE") or "auto"
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT", "300"))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "80"))
SESSION_KEY = "http_session"
BACKEND_KEY = "backend"


class RemoteApiError(RuntimeError):
    pass


def split_base_url(raw: str):
    """Split a studio URL into ``(origin, studio_token)``.

    A bare origin is the normal input. A full embed URL carrying
    ``?studio_token=xxx`` is still accepted so an existing setup keeps
    working, but a dedicated token key is the documented way in.
    """
    raw = (raw or "").strip()
    if not raw:
        return None, None
    if "//" not in raw:
        raw = f"https://{raw}"
    parts = urlsplit(raw)
    token = None
    for key, value in parse_qsl(parts.query):
        if key == "studio_token" and value:
            token = value
    return urlunsplit((parts.scheme or "https", parts.netloc, "", "", "")) or None, token


def slugify_model(model: str):
    """Normalise a model name into a token-key slug.

    ``Qwen3-ASR-1.7B``, ``qwen3-asr-1-7b`` and ``qwen3-asr-1.7b-hf`` all
    collapse onto ``qwen3-asr-1-7b`` so any spelling finds the same key.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", (model or "").lower()).strip("-")
    slug = re.sub(r"-(hf|studio|demo)$", "", slug)
    return slug


def load_studio_tokens():
    """Collect ``<model>-studio-token`` keys from the environment."""
    tokens = {}
    for key, value in os.environ.items():
        key = key.strip().lower().replace("_", "-")
        value = (value or "").strip()
        if not value or not key.endswith(TOKEN_SUFFIX):
            continue
        slug = slugify_model(key[: -len(TOKEN_SUFFIX)])
        if slug:
            tokens[slug] = value
    return tokens


STUDIO_TOKENS = load_studio_tokens()
_RAW_BASE_URL, _URL_TOKEN = split_base_url(os.getenv("BASE_URL"))
# A global fallback for callers that do not name a model.
STUDIO_TOKEN = (os.getenv("STUDIO_TOKEN") or _URL_TOKEN or "").strip()

# Configuring a studio token is enough: the studio origin is implied.
if _RAW_BASE_URL:
    BASE_URL = _RAW_BASE_URL
elif STUDIO_TOKENS or STUDIO_TOKEN:
    BASE_URL = STUDIO_BASE_URL
else:
    BASE_URL = DEMO_BASE_URL


def resolve_token(model: str):
    """Pick the token for ``model``, falling back to the global one."""
    if STUDIO_TOKENS:
        slug = slugify_model(model)
        if token := STUDIO_TOKENS.get(slug):
            return token
        # A single configured token serves an unnamed or mismatched model.
        if not STUDIO_TOKEN and len(STUDIO_TOKENS) == 1:
            return next(iter(STUDIO_TOKENS.values()))
    return STUDIO_TOKEN or None


def studio_headers(token: str):
    """Headers carrying the studio token, as the embed page sends it."""
    if not token:
        return None
    if not TOKEN_RE.match(token):
        raise RemoteApiError("Studio token contains unsupported characters")
    return {"Cookie": f"studio_token={token}", "X-Studio-Token": token}


TRUTHY = ("1", "true", "yes", "on")
FALSY = ("0", "false", "no", "off")

FORCE_BACKEND = (os.getenv("BACKEND") or "").strip().lower() or None

API_KEY = (os.getenv("API_KEY") or "").strip()
# Unset: require a key only when one is configured. true/false forces it on or
# off, so a key can be kept in the environment while auth is switched off.
_REQUIRE_RAW = (os.getenv("REQUIRE_API_KEY") or "").strip().lower()
if _REQUIRE_RAW in TRUTHY:
    REQUIRE_API_KEY = True
elif _REQUIRE_RAW in FALSY:
    REQUIRE_API_KEY = False
else:
    if _REQUIRE_RAW:
        _LOGGER.warning("Unrecognised REQUIRE_API_KEY %r, deriving from API_KEY", _REQUIRE_RAW)
    REQUIRE_API_KEY = bool(API_KEY)

# The model detects language itself, and a wrong client hint only mislabels the
# result, so client-sent `language` is ignored unless this is switched off.
TRUST_CLIENT_LANGUAGE = (os.getenv("TRUST_CLIENT_LANGUAGE") or "").strip().lower() in TRUTHY

# The demo app takes ISO codes ("en"), the studio app takes display names
# ("English"). Keyed by the ISO code the demo app uses.
LANGUAGES = {
    "zh": "Chinese",
    "yue": "Cantonese",
    "en": "English",
    "ar": "Arabic",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "pt": "Portuguese",
    "id": "Indonesian",
    "it": "Italian",
    "ko": "Korean",
    "ru": "Russian",
    "th": "Thai",
    "vi": "Vietnamese",
    "ja": "Japanese",
    "tr": "Turkish",
    "hi": "Hindi",
    "ms": "Malay",
    "nl": "Dutch",
    "sv": "Swedish",
    "da": "Danish",
    "fi": "Finnish",
    "pl": "Polish",
    "cs": "Czech",
    "fil": "Filipino",
    "fa": "Persian",
    "el": "Greek",
    "ro": "Romanian",
    "hu": "Hungarian",
    "mk": "Macedonian",
}
LANGUAGE_NAME_TO_CODE = {name.lower(): code for code, name in LANGUAGES.items()}
LANGUAGE_NAME_TO_CODE["tagalog"] = "fil"


def normalize_language(value: str, backend: str):
    """Map an OpenAI-style language hint onto what the active backend expects."""
    value = (value or "").strip()
    if not value or value.lower() in ("auto", "auto detect"):
        return "Auto" if backend == STUDIO_BACKEND else "auto"

    code = value.lower()
    if code not in LANGUAGES:
        code = LANGUAGE_NAME_TO_CODE.get(code)
    if code is None:
        _LOGGER.warning("Unknown language %r, falling back to auto detection", value)
        return "Auto" if backend == STUDIO_BACKEND else "auto"

    return LANGUAGES[code] if backend == STUDIO_BACKEND else code


async def init_session(app):
    if STUDIO_TOKENS:
        _LOGGER.info("Studio tokens configured for: %s", ", ".join(sorted(STUDIO_TOKENS)))
    elif STUDIO_TOKEN:
        _LOGGER.info("Global studio token configured")
    _LOGGER.info("Upstream: %s", BASE_URL)

    app[SESSION_KEY] = aiohttp.ClientSession(
        base_url=BASE_URL,
        timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
        headers={
            aiohttp.hdrs.USER_AGENT: USER_AGENT,
            aiohttp.hdrs.REFERER: f"{BASE_URL}/",
        },
    )
    app[BACKEND_KEY] = FORCE_BACKEND


async def on_cleanup(app):
    session = app.get(SESSION_KEY)
    if session and not session.closed:
        await session.close()


async def resolve_backend(app):
    """Detect which Gradio app is behind BASE_URL, caching the result."""
    backend = app.get(BACKEND_KEY)
    if backend:
        return backend

    session = app[SESSION_KEY]
    backend = STUDIO_BACKEND if "-demo." not in BASE_URL else DEMO_BACKEND
    try:
        token = STUDIO_TOKEN or (next(iter(STUDIO_TOKENS.values()), None))
        response = await session.get("/gradio_api/info", headers=studio_headers(token))
        if response.status == 200:
            endpoints = (await response.json()).get("named_endpoints") or {}
            if "/asr_inference" in endpoints:
                backend = DEMO_BACKEND
            elif "/transcribe" in endpoints:
                backend = STUDIO_BACKEND
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        _LOGGER.warning("Backend detection failed (%s), assuming %s", exc, backend)

    _LOGGER.info("Backend for %s: %s", BASE_URL, backend)
    app[BACKEND_KEY] = backend
    return backend


async def api_post(session: aiohttp.ClientSession, api: str, *, json_body=None, **kwargs):
    _LOGGER.info("%s: %s", api, json_body if json_body is not None else "<non-json-body>")
    return await session.post(api, json=json_body, **kwargs)


async def get_models(request):
    if not await check_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    backend = await resolve_backend(request.app)
    models = [{"id": "qwen3-asr"}]
    if backend == STUDIO_BACKEND:
        models.append({"id": "Qwen3-ASR-1.7B"})
    else:
        models.append({"id": "qwen3-asr:itn"})
    return web.json_response({"data": models})


async def read_part(audio_file: aiohttp.multipart.BodyPartReader):
    """Buffer an uploaded file part into ``(name, content_type, bytes)``."""
    file_bytes = bytearray()
    while True:
        chunk = await audio_file.read_chunk()
        if not chunk:
            break
        file_bytes.extend(chunk)

    if not file_bytes:
        _LOGGER.warning("No file provided. %s", audio_file)
        return None

    return (
        audio_file.filename or "audio",
        audio_file.headers.get(aiohttp.hdrs.CONTENT_TYPE, "application/octet-stream"),
        bytes(file_bytes),
    )


async def upload_file(session: aiohttp.ClientSession, audio, *, headers=None):
    if not audio:
        return None

    name, content_type, file_bytes = audio
    form = aiohttp.FormData()
    form.add_field("files", file_bytes, filename=name, content_type=content_type)

    response = await api_post(session, "/gradio_api/upload", data=form, headers=headers)
    body = await response.text()
    if response.status != 200:
        raise RemoteApiError(f"Remote upload failed ({response.status}): {body[:300]}")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RemoteApiError(f"Remote upload returned invalid JSON: {body[:300]}") from exc

    if not isinstance(payload, list) or not payload or not payload[0]:
        raise RemoteApiError(f"Remote upload returned unexpected payload: {body[:300]}")

    return payload[0]


async def run_inference(
    session: aiohttp.ClientSession,
    *,
    backend: str,
    audio_path: str,
    prompt: str,
    language: str,
    enable_itn: bool,
    with_timestamps: bool,
    headers=None,
):
    audio = {"path": audio_path, "meta": {"_type": "gradio.FileData"}}
    if backend == STUDIO_BACKEND:
        api = "/gradio_api/run/transcribe"
        payload = {"data": [audio, language, with_timestamps]}
    else:
        api = "/gradio_api/run/asr_inference"
        payload = {"data": [audio, prompt, language, enable_itn]}

    response = await api_post(session, api, json_body=payload, headers=headers)
    body = await response.text()
    if response.status != 200:
        raise RemoteApiError(f"Remote inference failed ({response.status}): {body[:300]}")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RemoteApiError(f"Remote inference returned invalid JSON: {body[:300]}") from exc

    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise RemoteApiError(f"Remote inference returned unexpected payload: {body[:300]}")

    # The studio app returns [lang, text, timestamps, viz], the demo app [text, lang].
    if backend == STUDIO_BACKEND:
        lang = data[0] if isinstance(data[0], str) else None
        text = data[1] if len(data) > 1 else None
        words = data[2] if len(data) > 2 and isinstance(data[2], list) else None
    else:
        text = data[0]
        lang = data[1] if len(data) > 1 else None
        words = None

    if not isinstance(text, str):
        raise RemoteApiError(f"Remote inference returned unexpected payload: {body[:300]}")

    _LOGGER.info("Remote result: text=%r lang=%r words=%d", text, lang, len(words or []))
    return text, lang, words


def convert_words(words):
    """Reshape Gradio word timestamps into OpenAI-style word objects."""
    result = []
    for item in words or []:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "word": item.get("text", ""),
                "start": item.get("start_time"),
                "end": item.get("end_time"),
            }
        )
    return result


async def transcribe(request):
    if request.method == "OPTIONS":
        return web.Response(status=204)
    if request.method != "POST":
        return web.json_response({"error": "Method not allowed"}, status=405)
    if not await check_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    _LOGGER.info("%s", request.rel_url)
    try:
        reader = await request.multipart()
    except (ValueError, AssertionError) as exc:
        # aiohttp asserts on a non-multipart content type rather than raising.
        _LOGGER.warning("Invalid multipart payload: %s", exc)
        return web.json_response(
            {
                "error": "Invalid multipart/form-data payload. If using curl with -F, do not set Content-Type manually; let curl generate the boundary.",
            },
            status=400,
        )

    post = {}
    audio = None
    session = request.app[SESSION_KEY]
    backend = await resolve_backend(request.app)

    while True:
        part = await reader.next()
        if part is None:
            break
        if part.name == "file":
            # Buffered, not uploaded yet: the token depends on `model`, which
            # may arrive after the file part.
            audio = await read_part(part)
        else:
            post[part.name] = await part.text()

    if not audio:
        return web.json_response({"error": "No file provided"}, status=400)

    model = (post.get("model") or "").strip()
    prompt = post.get("prompt", "")
    # Clients like Home Assistant always send their configured language, which
    # is wrong the moment someone speaks another one. Auto-detect instead.
    requested = post.get("language")
    if requested and not TRUST_CLIENT_LANGUAGE:
        _LOGGER.info("Ignoring client language %r in favour of auto detection", requested)
        requested = None
    language = normalize_language(requested or DEFAULT_LANGUAGE, backend)
    enable_itn = model.endswith("itn")
    want_words = post.get("response_format") == "verbose_json" or "word" in post.get(
        "timestamp_granularities[]", post.get("timestamp_granularities", "")
    )

    try:
        headers = studio_headers(resolve_token(model)) if backend == STUDIO_BACKEND else None
        audio_path = await upload_file(session, audio, headers=headers)
        if not audio_path:
            return web.json_response({"error": "No file provided"}, status=400)
        text, lang, words = await run_inference(
            session,
            backend=backend,
            audio_path=audio_path,
            prompt=prompt,
            language=language,
            enable_itn=enable_itn,
            with_timestamps=want_words,
            headers=headers,
        )
    except RemoteApiError as exc:
        _LOGGER.error("Transcription failed: %s", exc)
        return web.json_response({"error": str(exc)}, status=502)

    response = {"text": text}
    if lang is not None:
        response["lang"] = lang
    if want_words and words:
        response["words"] = convert_words(words)
    return web.json_response(response)


async def check_auth(request):
    if not REQUIRE_API_KEY:
        return True

    presented = request.headers.get(aiohttp.hdrs.AUTHORIZATION, "").strip()
    if presented.lower().startswith("bearer "):
        presented = presented[7:].strip()
    # compare_digest keeps the check constant-time.
    return bool(presented) and secrets.compare_digest(presented, API_KEY)


@web.middleware
async def cors_auth_middleware(request, handler):
    if request.method == "OPTIONS":
        response = web.Response(status=204)
    else:
        response = await handler(request)
    response.headers[aiohttp.hdrs.ACCESS_CONTROL_ALLOW_ORIGIN] = "*"
    response.headers[aiohttp.hdrs.ACCESS_CONTROL_ALLOW_METHODS] = "GET, POST, OPTIONS"
    response.headers[aiohttp.hdrs.ACCESS_CONTROL_ALLOW_HEADERS] = "Content-Type, Authorization"
    return response


def create_app():
    if REQUIRE_API_KEY and not API_KEY:
        raise SystemExit("REQUIRE_API_KEY is set but API_KEY is empty; nothing could authenticate.")
    if REQUIRE_API_KEY:
        _LOGGER.info("API key required for /v1/models and /v1/audio/transcriptions")
    else:
        _LOGGER.warning(
            "No API key required: this service is open to anyone who can reach %s:%s", HOST, PORT
        )

    app = web.Application(logger=_LOGGER, middlewares=[cors_auth_middleware])
    app.on_startup.append(init_session)
    app.on_cleanup.append(on_cleanup)
    app.router.add_get("/v1/models", get_models)
    app.router.add_route("*", "/v1/audio/transcriptions", transcribe)
    return app


def main():
    web.run_app(create_app(), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
