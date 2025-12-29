import os
import aiohttp
import logging
from aiohttp import web
from gradio_client import Client, handle_file

logging.basicConfig(level=logging.WARNING)
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)
BASE_URL = os.getenv("BASE_URL") or "https://qwen-qwen3-asr-demo.ms.show"
USER_AGENT = "Mozilla/5.0 AppleWebKit/537.36 Chrome/143 Safari/537"

SESSION = None

async def init_session(app):
    global SESSION
    SESSION = aiohttp.ClientSession(
        base_url=BASE_URL,
    )

async def api_request(api, json=None, headers=None, **kwargs):
    _LOGGER.info("%s: %s", api, json)
    return await SESSION.post(
        api,
        json=json,
        headers={
            aiohttp.hdrs.USER_AGENT: USER_AGENT,
            aiohttp.hdrs.REFERER: BASE_URL,
            **(headers or {}),
        },
        **kwargs,
    )

async def get_models(request):
    models = [
        {"id": "qwen-qwen3-asr"},
        {"id": "qwen-qwen3-asr:itn"},
    ]
    return web.json_response({"data": models})

async def upload_file(audio_file: aiohttp.multipart.BodyPartReader):
    if not audio_file:
        return None
    name = audio_file.filename or "audio"
    file = b""
    while True:
        chunk = await audio_file.read_chunk()
        if not chunk:
            break
        file += chunk
    if not file:
        _LOGGER.warning("No file provided. %s", audio_file)
        return None
    form = aiohttp.FormData()
    form.add_field("files", file, filename=name)
    res = await api_request("/gradio_api/upload", data=form)
    try:
        src = (await res.json())[0]
        if not src:
            _LOGGER.warning("Upload failed: %s", [res.status, await res.text()])
    except:
        src = None
        _LOGGER.error("Upload failed: %s", [res.status, await res.text()], exc_info=True)
    return src

async def transcribe(request):
    if not await check_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)
    _LOGGER.info("%s", request.rel_url)
    reader = await request.multipart()
    post = {}
    audio_path = None
    while True:
        part = await reader.next()
        if part is None:
            break
        if part.name == "file":
            audio_path = await upload_file(part)
        else:
            post[part.name] = await part.text()
    if not audio_path:
        return web.json_response({"error": "No file provided"}, status=400)
    audio_url = f"https://qwen-qwen3-asr-demo.ms.show/gradio_api/file={audio_path}"
    res = await SESSION.get(audio_url)
    _LOGGER.info("Audio file: %s", [audio_url, res.status, res.headers])

    gradio = Client(BASE_URL)
    result = gradio.predict(
		audio_file=handle_file(audio_url),
		context=post.get("prompt", ""),
		language="auto",
		enable_itn=post.get("model", "").endswith("itn"),
		api_name="/asr_inference",
    )
    gradio.close()
    _LOGGER.info("Gradio result: %s", result)
    return web.json_response({
        "text" : result[0],
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
    request.response_factory = lambda: web.StreamResponse()
    response = await handler(request)
    response.headers[aiohttp.hdrs.ACCESS_CONTROL_ALLOW_ORIGIN] = "*"
    response.headers[aiohttp.hdrs.ACCESS_CONTROL_ALLOW_METHODS] = "GET, POST, OPTIONS"
    response.headers[aiohttp.hdrs.ACCESS_CONTROL_ALLOW_HEADERS] = "Content-Type, Authorization"
    return response

app = web.Application(logger=_LOGGER, middlewares=[cors_auth_middleware])
app.on_startup.append(init_session)

app.router.add_get("/v1/models", get_models)
app.router.add_route("*", "/v1/audio/transcriptions", transcribe)

async def on_cleanup(app):
    if SESSION:
        await SESSION.close()
app.on_cleanup.append(on_cleanup)

web.run_app(app, host="0.0.0.0", port=80)
