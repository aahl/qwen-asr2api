import os
import time
import unittest

from aiohttp import FormData
from aiohttp.test_utils import TestClient, TestServer

import asr2api


class _AlwaysEofGradio:
    def __init__(self):
        self.calls = 0

    def predict(self, **kwargs):
        self.calls += 1
        raise RuntimeError("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol")


class _SlowGradio:
    def predict(self, **kwargs):
        time.sleep(0.2)
        return ("ok", "中文 / Chinese")


class TranscribeApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._orig_gradio = asr2api.GRADIO
        self._orig_retries = asr2api.UPSTREAM_RETRIES
        self._orig_backoff = asr2api.UPSTREAM_RETRY_BACKOFF_SEC
        self._orig_timeout = asr2api.UPSTREAM_TIMEOUT_SEC
        self._orig_api_key = os.environ.get("API_KEY")

        os.environ["API_KEY"] = "test-key"
        asr2api.UPSTREAM_RETRIES = 1
        asr2api.UPSTREAM_RETRY_BACKOFF_SEC = 0
        asr2api.UPSTREAM_TIMEOUT_SEC = 1

        self.app = asr2api.create_app(init_upstream=False)
        self.server = TestServer(self.app)
        self.client = TestClient(self.server)
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

        asr2api.GRADIO = self._orig_gradio
        asr2api.UPSTREAM_RETRIES = self._orig_retries
        asr2api.UPSTREAM_RETRY_BACKOFF_SEC = self._orig_backoff
        asr2api.UPSTREAM_TIMEOUT_SEC = self._orig_timeout

        if self._orig_api_key is None:
            os.environ.pop("API_KEY", None)
        else:
            os.environ["API_KEY"] = self._orig_api_key

    async def test_non_multipart_request_returns_400(self):
        resp = await self.client.post(
            "/v1/audio/transcriptions",
            json={"model": "qwen3-asr"},
            headers={"Authorization": "Bearer test-key"},
        )
        self.assertEqual(resp.status, 400)
        body = await resp.json()
        self.assertIn("multipart/form-data", body["error"])

    async def test_transient_upstream_error_returns_502(self):
        failing = _AlwaysEofGradio()
        asr2api.GRADIO = failing

        data = FormData()
        data.add_field("model", "qwen3-asr")
        data.add_field("file", b"fake-wav-bytes", filename="audio.wav", content_type="audio/wav")

        resp = await self.client.post(
            "/v1/audio/transcriptions",
            data=data,
            headers={"Authorization": "Bearer test-key"},
        )

        self.assertEqual(resp.status, 502)
        body = await resp.json()
        self.assertEqual(body["error"], "Upstream ASR unavailable")
        self.assertEqual(failing.calls, asr2api.UPSTREAM_RETRIES + 1)

    async def test_upstream_timeout_returns_504(self):
        asr2api.GRADIO = _SlowGradio()
        asr2api.UPSTREAM_TIMEOUT_SEC = 0.05

        data = FormData()
        data.add_field("model", "qwen3-asr")
        data.add_field("file", b"fake-wav-bytes", filename="audio.wav", content_type="audio/wav")

        resp = await self.client.post(
            "/v1/audio/transcriptions",
            data=data,
            headers={"Authorization": "Bearer test-key"},
        )

        self.assertEqual(resp.status, 504)
        body = await resp.json()
        self.assertEqual(body["error"], "Upstream ASR timeout")


if __name__ == "__main__":
    unittest.main()
