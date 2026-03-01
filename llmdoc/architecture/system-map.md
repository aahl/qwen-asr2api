# 系统映射

## 1. 身份
- **是什么：** 单进程 aiohttp 网关，负责鉴权、上传解析、上游调用、错误映射。
- **用途：** 把 Gradio 推理接口标准化为稳定的 OpenAI 风格语音转写 API。

## 2. 核心组件
- [`asr2api/__init__.py:24`](/Users/caike/3.工具/qwen-asr2api/asr2api/__init__.py:24) `init_session`：启动时初始化 `aiohttp.ClientSession` 与 Gradio Client。
- [`asr2api/__init__.py:108`](/Users/caike/3.工具/qwen-asr2api/asr2api/__init__.py:108) `transcribe`：主处理逻辑，执行鉴权、multipart 校验、文件读取、上游调用。
- [`asr2api/__init__.py:68`](/Users/caike/3.工具/qwen-asr2api/asr2api/__init__.py:68) `_is_retryable_upstream_error`：判定可重试的上游异常。
- [`asr2api/__init__.py:90`](/Users/caike/3.工具/qwen-asr2api/asr2api/__init__.py:90) `_predict_with_retry`：指数退避重试。
- [`asr2api/__init__.py:193`](/Users/caike/3.工具/qwen-asr2api/asr2api/__init__.py:193) `cors_auth_middleware`：处理 CORS 响应头。
- [`tests/test_transcriptions.py:57`](/Users/caike/3.工具/qwen-asr2api/tests/test_transcriptions.py:57) 起：回归测试覆盖 400/502/504。

## 3. 执行流程
1. **启动：** `create_app()` 注册路由与生命周期回调（[`asr2api/__init__.py:212`](/Users/caike/3.工具/qwen-asr2api/asr2api/__init__.py:212)）。
2. **请求入口：** `POST /v1/audio/transcriptions` 进入 `transcribe`（[`asr2api/__init__.py:220`](/Users/caike/3.工具/qwen-asr2api/asr2api/__init__.py:220)）。
3. **输入校验：** 非 `multipart/form-data` 直接 400（[`asr2api/__init__.py:115`](/Users/caike/3.工具/qwen-asr2api/asr2api/__init__.py:115)）。
4. **上游调用：** 在线程池执行 `_predict_with_retry`，并由 `asyncio.wait_for` 控制超时（[`asr2api/__init__.py:153`](/Users/caike/3.工具/qwen-asr2api/asr2api/__init__.py:153)）。
5. **错误映射：** 超时返回 504，其他上游故障返回 502（[`asr2api/__init__.py:163`](/Users/caike/3.工具/qwen-asr2api/asr2api/__init__.py:163)）。
6. **成功响应：** 返回 `text/message` 与 `lang` 字段（[`asr2api/__init__.py:179`](/Users/caike/3.工具/qwen-asr2api/asr2api/__init__.py:179)）。
