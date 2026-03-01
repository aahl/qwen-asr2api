# 常用工作流

1. 构建并启动：在项目根目录运行 `docker compose up -d --build`，若 compose 仅使用远程镜像，需额外指定 build override。
2. 健康检查：查看容器状态 `docker compose ps`，重点确认 `asr2api` 为 `healthy`。
3. API 自检：请求 `GET /v1/models`，预期 200 与模型列表（路由定义见 [`asr2api/__init__.py:220`](/Users/caike/3.工具/qwen-asr2api/asr2api/__init__.py:220)）。
4. 回归测试：运行 `python -m unittest -v tests/test_transcriptions.py`，验证 400/502/504 行为（用例见 [`tests/test_transcriptions.py:57`](/Users/caike/3.工具/qwen-asr2api/tests/test_transcriptions.py:57)）。
5. 异常排查：优先看容器日志中 `Upstream ASR` 与 `UNEXPECTED_EOF` 关键字，对照重试与超时配置（变量定义见 [`asr2api/__init__.py:16`](/Users/caike/3.工具/qwen-asr2api/asr2api/__init__.py:16)）。
