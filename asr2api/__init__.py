import os
import time
import asyncio
import tempfile
import aiohttp
import logging
from aiohttp import web
from gradio_client import Client, handle_file

logging.basicConfig(level=logging.WARNING)
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)
BASE_URL = os.getenv("BASE_URL") or "https://qwen-qwen3-asr-demo.ms.show"
USER_AGENT = "Mozilla/5.0 AppleWebKit/537.36 Chrome/143 Safari/537"
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
UPSTREAM_TIMEOUT_SEC = float(os.getenv("UPSTREAM_TIMEOUT_SEC") or 45)
UPSTREAM_RETRIES = int(os.getenv("UPSTREAM_RETRIES") or 2)
UPSTREAM_RETRY_BACKOFF_SEC = float(os.getenv("UPSTREAM_RETRY_BACKOFF_SEC") or 0.8)
MAX_BACKOFF_SEC = 5.0

SESSION = None
GRADIO = None

async def init_session(app):
    global SESSION, GRADIO
    SESSION = aiohttp.ClientSession(
        base_url=BASE_URL,
    )
    _LOGGER.info("Initializing Gradio client (one-time)...")
    t0 = time.monotonic()
    GRADIO = Client(BASE_URL)
    _LOGGER.info("Gradio client ready in %.1fs", time.monotonic() - t0)

async def get_models(request):
    models = [
        {"id": "qwen-qwen3-asr"},
        {"id": "qwen-qwen3-asr:itn"},
    ]
    return web.json_response({"data": models})

async def read_audio(audio_file: aiohttp.multipart.BodyPartReader):
    if not audio_file:
        return None, None
    name = audio_file.filename or "audio.wav"
    data = b""
    while True:
        chunk = await audio_file.read_chunk()
        if not chunk:
            break
        data += chunk
        if len(data) > MAX_FILE_SIZE:
            _LOGGER.warning("File too large: %s (%d bytes)", name, len(data))
            return None, None
    if not data:
        _LOGGER.warning("No file provided. %s", audio_file)
        return None, None
    return name, data

def _do_predict(tmp_path, context, enable_itn):
    return GRADIO.predict(
        audio_file=handle_file(tmp_path),
        context=context,
        language="auto",
        enable_itn=enable_itn,
        api_name="/asr_inference",
    )

def _is_retryable_upstream_error(exc: Exception) -> bool:
    retryable_names = {
        "ConnectError",
        "ReadError",
        "WriteError",
        "ReadTimeout",
        "WriteTimeout",
        "TimeoutException",
        "RemoteProtocolError",
        "ProtocolError",
        "NetworkError",
        "TransportError",
    }
    cur = exc
    while cur:
        if cur.__class__.__name__ in retryable_names:
            return True
        if "UNEXPECTED_EOF_WHILE_READING" in str(cur):
            return True
        cur = cur.__cause__
    return False

def _predict_with_retry(tmp_path, context, enable_itn):
    attempts = max(1, UPSTREAM_RETRIES + 1)
    for attempt in range(1, attempts + 1):
        try:
            return _do_predict(tmp_path, context, enable_itn)
        except Exception as exc:
            if attempt == attempts or not _is_retryable_upstream_error(exc):
                raise
            sleep_s = min(UPSTREAM_RETRY_BACKOFF_SEC * (2 ** (attempt - 1)), MAX_BACKOFF_SEC)
            _LOGGER.warning(
                "Upstream error on attempt %d/%d, retry in %.2fs: %s",
                attempt,
                attempts,
                sleep_s,
                exc,
            )
            time.sleep(sleep_s)

async def transcribe(request):
    if not await check_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    t_start = time.monotonic()
    _LOGGER.info("%s", request.rel_url)

    if not request.content_type.startswith("multipart/"):
        return web.json_response(
            {"error": "Content-Type must be multipart/form-data"},
            status=400,
        )

    try:
        reader = await request.multipart()
    except AssertionError:
        return web.json_response(
            {"error": "Content-Type must be multipart/form-data"},
            status=400,
        )

    post = {}
    audio_name = None
    audio_data = None
    while True:
        part = await reader.next()
        if part is None:
            break
        if part.name == "file":
            audio_name, audio_data = await read_audio(part)
        else:
            post[part.name] = await part.text()
    if not audio_data:
        return web.json_response({"error": "No file provided"}, status=400)

    t_parsed = time.monotonic()
    _LOGGER.info("Parsed audio: %s (%d bytes) in %.2fs", audio_name, len(audio_data), t_parsed - t_start)

    suffix = os.path.splitext(audio_name)[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name

    try:
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                _predict_with_retry,
                tmp_path,
                post.get("prompt", ""),
                post.get("model", "").endswith("itn"),
            ),
            timeout=UPSTREAM_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        _LOGGER.warning("Upstream ASR timeout after %.1fs", UPSTREAM_TIMEOUT_SEC)
        return web.json_response({"error": "Upstream ASR timeout"}, status=504)
    except Exception as exc:
        _LOGGER.exception("Upstream ASR request failed: %s", exc)
        return web.json_response({"error": "Upstream ASR unavailable"}, status=502)
    finally:
        os.unlink(tmp_path)

    t_done = time.monotonic()
    _LOGGER.info("Gradio result in %.2fs (total %.2fs): %s", t_done - t_parsed, t_done - t_start, result)

    if not isinstance(result, (list, tuple)) or len(result) < 2:
        _LOGGER.warning("Invalid upstream result payload: %s", result)
        return web.json_response({"error": "Invalid upstream response"}, status=502)

    text_field = "text" if result and result[1] is not None else "message"
    return web.json_response({
        text_field : result[0],
        "lang" : result[1],
    })

async def check_auth(request):
    if apikey := os.getenv("API_KEY"):
        auth_header = request.headers.get("Authorization", "")
        if auth_header not in [apikey, f"Bearer {apikey}"]:
            return False
    return True


@web.middleware
async def cors_auth_middleware(request, handler):
    response = await handler(request)
    allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost,http://127.0.0.1")
    origin = request.headers.get("Origin", "")
    for allowed in allowed_origins.split(","):
        if origin.startswith(allowed.strip()):
            response.headers[aiohttp.hdrs.ACCESS_CONTROL_ALLOW_ORIGIN] = origin
            break
    response.headers[aiohttp.hdrs.ACCESS_CONTROL_ALLOW_METHODS] = "GET, POST, OPTIONS"
    response.headers[aiohttp.hdrs.ACCESS_CONTROL_ALLOW_HEADERS] = "Content-Type, Authorization"
    return response

async def on_cleanup(app):
    if SESSION:
        await SESSION.close()
    if GRADIO and hasattr(GRADIO, "close"):
        GRADIO.close()

def create_app(init_upstream=True):
    app = web.Application(
        logger=_LOGGER,
        middlewares=[cors_auth_middleware],
        client_max_size=MAX_FILE_SIZE,
    )
    if init_upstream:
        app.on_startup.append(init_session)
    app.router.add_get("/v1/models", get_models)
    app.router.add_route("*", "/v1/audio/transcriptions", transcribe)
    app.on_cleanup.append(on_cleanup)
    return app

def main():
    web.run_app(create_app(), host="0.0.0.0", port=80)
