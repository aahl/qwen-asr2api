# 运行约定

## 1. 核心摘要
- API 兼容风格：面向 OpenAI Speech API，核心端点是 `/v1/audio/transcriptions`（[`README.md:41`](/Users/caike/3.工具/qwen-asr2api/README.md:41)）。
- 默认上游地址：`https://qwen-qwen3-asr-demo.ms.show`（[`asr2api/__init__.py:13`](/Users/caike/3.工具/qwen-asr2api/asr2api/__init__.py:13)）。
- 鉴权约定：若设置 `API_KEY`，支持 `Authorization: <key>` 或 `Authorization: Bearer <key>`（[`asr2api/__init__.py:185`](/Users/caike/3.工具/qwen-asr2api/asr2api/__init__.py:185)）。
- 端口约定：容器内监听 `80`，示例 compose 映射到 `127.0.0.1:8820`（[`asr2api/__init__.py:225`](/Users/caike/3.工具/qwen-asr2api/asr2api/__init__.py:225)、[`docker-compose.yml:6`](/Users/caike/3.工具/qwen-asr2api/docker-compose.yml:6)）。

## 2. 信息源
- [`asr2api/__init__.py`](/Users/caike/3.工具/qwen-asr2api/asr2api/__init__.py)：服务主逻辑与容错策略。
- [`tests/test_transcriptions.py`](/Users/caike/3.工具/qwen-asr2api/tests/test_transcriptions.py)：容错行为回归测试。
- [`Dockerfile`](/Users/caike/3.工具/qwen-asr2api/Dockerfile)：运行时镜像与进程入口。
- [`docker-compose.yml`](/Users/caike/3.工具/qwen-asr2api/docker-compose.yml)：默认部署编排。
