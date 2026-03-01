# 项目概览

## 1. 身份
- **是什么：** 一个将 Qwen ASR Gradio 服务适配为 OpenAI 风格 STT API 的轻量网关。
- **用途：** 对外提供 `/v1/models` 与 `/v1/audio/transcriptions`，并转发到上游 `qwen-qwen3-asr-demo.ms.show`。

## 2. 概述
- 服务入口由 [`asr2api/__main__.py:1`](/Users/caike/3.工具/qwen-asr2api/asr2api/__main__.py:1) 调用 `main()`，最终运行 aiohttp 应用见 [`asr2api/__init__.py:225`](/Users/caike/3.工具/qwen-asr2api/asr2api/__init__.py:225)。
- 主要依赖为 `aiohttp` 与 `gradio_client`，定义在 [`pyproject.toml:7`](/Users/caike/3.工具/qwen-asr2api/pyproject.toml:7)。
- 默认部署模式以容器运行，基础镜像与启动命令见 [`Dockerfile:1`](/Users/caike/3.工具/qwen-asr2api/Dockerfile:1) 和 [`Dockerfile:16`](/Users/caike/3.工具/qwen-asr2api/Dockerfile:16)。
- 示例编排文件默认发布 `127.0.0.1:8820`，配置见 [`docker-compose.yml:6`](/Users/caike/3.工具/qwen-asr2api/docker-compose.yml:6)。
