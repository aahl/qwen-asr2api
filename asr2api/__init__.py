import json
import logging
import os

import aiohttp
from aiohttp import web

logging.basicConfig(level=logging.WARNING)
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)

BASE_URL = os.getenv("BASE_URL") or "https://qwen-qwen3-asr-demo.ms.show"
USER_AGENT = "Mozilla/5.0 AppleWebKit/537.36 Chrome/143 Safari/537"
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE") or "auto"
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT", "300"))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "80"))
SESSION_KEY = "http_session"


class RemoteApiError(RuntimeError):
    pass


async def init_session(app):
    app[SESSION_KEY] = aiohttp.ClientSession(
        base_url=BASE_URL,
        timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
        headers={
            aiohttp.hdrs.USER_AGENT: USER_AGENT,
            aiohttp.hdrs.REFERER: BASE_URL,
        },
    )


async def on_cleanup(app):
    session = app.get(SESSION_KEY)
    if session and not session.closed:
        await session.close()


async def api_post(session: aiohttp.ClientSession, api: str, *, json_body=None, **kwargs):
    _LOGGER.info("%s: %s", api, json_body if json_body is not None else "<non-json-body>")
    return await session.post(api, json=json_body, **kwargs)


async def get_models(request):
    return web.json_response(
        {
            "data": [
                {"id": "qwen3-asr"},
                {"id": "qwen3-asr:itn"},
            ]
        }
    )


async def upload_file(session: aiohttp.ClientSession, audio_file: aiohttp.multipart.BodyPartReader):
    if not audio_file:
        return None

    name = audio_file.filename or "audio"
    file_bytes = bytearray()
    while True:
        chunk = await audio_file.read_chunk()
        if not chunk:
            break
        file_bytes.extend(chunk)

    if not file_bytes:
        _LOGGER.warning("No file provided. %s", audio_file)
        return None

    form = aiohttp.FormData()
    form.add_field(
        "files",
        bytes(file_bytes),
        filename=name,
        content_type=audio_file.headers.get(
            aiohttp.hdrs.CONTENT_TYPE,
            "application/octet-stream",
        ),
    )

    response = await api_post(session, "/gradio_api/upload", data=form)
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
    audio_path: str,
    prompt: str,
    language: str,
    enable_itn: bool,
):
    payload = {
        "data": [
            {
                "path": audio_path,
                "meta": {"_type": "gradio.FileData"},
            },
            prompt,
            language,
            enable_itn,
        ]
    }

    response = await api_post(session, "/gradio_api/run/asr_inference", json_body=payload)
    body = await response.text()
    if response.status != 200:
        raise RemoteApiError(f"Remote inference failed ({response.status}): {body[:300]}")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RemoteApiError(f"Remote inference returned invalid JSON: {body[:300]}") from exc

    data = payload.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], str):
        raise RemoteApiError(f"Remote inference returned unexpected payload: {body[:300]}")

    text = data[0]
    lang = data[1] if len(data) > 1 else None
    _LOGGER.info("Remote result: text=%r lang=%r", text, lang)
    return text, lang


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
    except ValueError as exc:
        _LOGGER.warning("Invalid multipart payload: %s", exc)
        return web.json_response(
            {
                "error": "Invalid multipart/form-data payload. If using curl with -F, do not set Content-Type manually; let curl generate the boundary.",
            },
            status=400,
        )

    post = {}
    audio_path = None
    session = request.app[SESSION_KEY]

    while True:
        part = await reader.next()
        if part is None:
            break
        if part.name == "file":
            audio_path = await upload_file(session, part)
        else:
            post[part.name] = await part.text()

    if not audio_path:
        return web.json_response({"error": "No file provided"}, status=400)

    model = (post.get("model") or "").strip()
    prompt = post.get("prompt", "")
    language = (post.get("language") or DEFAULT_LANGUAGE).strip() or DEFAULT_LANGUAGE
    enable_itn = model.endswith("itn")

    try:
        text, lang = await run_inference(
            session,
            audio_path=audio_path,
            prompt=prompt,
            language=language,
            enable_itn=enable_itn,
        )
    except RemoteApiError as exc:
        _LOGGER.error("Transcription failed: %s", exc)
        return web.json_response({"error": str(exc)}, status=502)

    response = {"text": text}
    if lang is not None:
        response["lang"] = lang
    return web.json_response(response)


async def check_auth(request):
    if apikey := os.getenv("API_KEY"):
        auth_header = request.headers.get("Authorization", "")
        if auth_header not in [apikey, f"Bearer {apikey}"]:
            return False
    return True


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
