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

async def transcribe(request):
    if not await check_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    t_start = time.monotonic()
    _LOGGER.info("%s", request.rel_url)

    reader = await request.multipart()
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
        result = await loop.run_in_executor(
            None,
            _do_predict,
            tmp_path,
            post.get("prompt", ""),
            post.get("model", "").endswith("itn"),
        )
    finally:
        os.unlink(tmp_path)

    t_done = time.monotonic()
    _LOGGER.info("Gradio result in %.2fs (total %.2fs): %s", t_done - t_parsed, t_done - t_start, result)

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

app = web.Application(
    logger=_LOGGER,
    middlewares=[cors_auth_middleware],
    client_max_size=MAX_FILE_SIZE,
)
app.on_startup.append(init_session)

app.router.add_get("/v1/models", get_models)
app.router.add_route("*", "/v1/audio/transcriptions", transcribe)

async def on_cleanup(app):
    if SESSION:
        await SESSION.close()
    if GRADIO:
        GRADIO.close()
app.on_cleanup.append(on_cleanup)

web.run_app(app, host="0.0.0.0", port=80)
