# 🎤 Qwen ASR

## Install / 安装

### 🐳 Docker compose
```shell
mkdir /opt/asr2api
cd /opt/asr2api
wget https://raw.githubusercontent.com/aahl/qwen-asr2api/refs/heads/main/docker-compose.yml
docker compose up -d
```

> 想用创空间后端，请下载本分支的 compose 文件（含令牌示例）：
> `wget https://raw.githubusercontent.com/osscv/qwen-asr2api/refs/heads/main/docker-compose.yml`

### 🐳 Docker run
```shell
docker run -d \
  --name asr2api \
  --restart=unless-stopped \
  -p 8820:80 \
  ghcr.nju.edu.cn/aahl/qwen-asr2api:main
```

> ⚠️ 上游镜像暂未包含 Qwen3-ASR-1.7B 创空间支持（[PR #4](https://github.com/aahl/qwen-asr2api/pull/4) 合并后即可用）。现在就想用创空间后端和词级时间戳，请改用本分支构建的镜像：
>
> ```shell
> docker run -d \
>   --name asr2api \
>   --restart=unless-stopped \
>   -p 8820:80 \
>   -e qwen3-asr-1-7b-studio-token=your-token \
>   ghcr.io/osscv/qwen-asr2api:main
> ```

### 🏠 Home Assistant OS Add-on
1. 添加加载项仓库
   * 打开 HomeAssistant，点击左侧菜单的 **配置 (Settings)** -> **加载项 (Add-ons)**
   * 点击右下角的 **加载项商店 (Add-on Store)**
   * 点击右上角的三个点 -> **仓库 (Repositories)**
   * 在输入框填入：`https://gitee.com/hasscc/addons`, 点击添加
   [![添加加载项仓库](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgitee.com%2Fhasscc%2Faddons)

2. **安装加载项**：
   * 刷新页面，找到并点击 **`Qwen ASR`**
   * 点击 **安装 (Install)**
   * 启动并设置开机启动


## 💻 Usage / 使用

### 🌐 CURL调用示例
```shell
curl --request POST \
  --url http://localhost:8820/v1/audio/transcriptions \
  --form model=qwen3-asr \
  --form file='@audio.wav'
```

> 注意：如果你用 `curl -F/--form`，不要手动设置 `Content-Type: multipart/form-data`，让 curl 自己生成带 boundary 的请求头。否则服务端会因为缺少 boundary 而拒绝请求。

### 🏠 Home Assistant
1. 安装 AI Conversation 集成
   > 点击这里 [一键安装](https://my.home-assistant.io/redirect/hacs_repository/?category=integration&owner=hasscc&repository=ai-conversation)，安装完记得重启HA
2. [添加 AI Conversation 服务](https://my.home-assistant.io/redirect/config_flow_start/?domain=ai_conversation)，配置模型提供商
   > 服务商: 自定义; 接口: `http://4e0de88e-qwen-asr/v1`; 密钥留空
   >
   > 若设置了 `API_KEY`（见 [访问密钥](#-api-key--访问密钥)），这里要填相同的密钥，否则会返回 401
3. 添加STT模型
4. 配置语音助手

## 🤖 Models / 模型
- `qwen3-asr`
- `qwen3-asr:itn` 启用逆文本标准化（仅默认 demo 后端支持）
- `Qwen3-ASR-1.7B` 使用 `qwen-qwen3-asr.ms.show` 后端时的模型名

## ⚙️ Environment / 环境变量
| 变量 | 说明 |
| --- | --- |
| `API_KEY` | 本服务的访问密钥（不是 Qwen 的密钥），留空则不校验 |
| `REQUIRE_API_KEY` | 是否强制校验密钥；留空时按 `API_KEY` 是否设置自动决定 |
| `<模型名>-studio-token` | 创空间令牌，如 `qwen3-asr-1-7b-studio-token`，配置后自动切换到该后端 |
| `STUDIO_TOKEN` | 全局令牌，适用于未指定 `model` 的调用 |
| `BASE_URL` | 转发目标，默认 `https://qwen-qwen3-asr-demo.ms.show`；配置了令牌则默认创空间 |
| `BACKEND` | 强制后端类型：`demo` 或 `studio`，默认自动探测 |
| `DEFAULT_LANGUAGE` | 默认语言，默认 `auto`（自动识别） |
| `TRUST_CLIENT_LANGUAGE` | 是否采纳客户端传来的 `language`，默认 `false` |
| `REQUEST_TIMEOUT` | 请求超时秒数，默认 `300` |
| `HOST` | 监听地址，默认 `0.0.0.0` |
| `PORT` | 监听端口，默认 `80`（容器内） |

### 🔑 API Key / 访问密钥
默认**不校验**密钥，任何能访问到端口的人都能调用。设置 `API_KEY` 即开启校验，`/v1/models` 和 `/v1/audio/transcriptions` 都会被保护：

```shell
docker run -d --name asr2api -p 8820:80 \
  -e API_KEY=sk-your-own-key \
  -e qwen3-asr-1-7b-studio-token=your-token \
  ghcr.io/osscv/qwen-asr2api:main
```

调用时用标准 OpenAI 写法，`Authorization: Bearer sk-your-own-key`（不带 `Bearer` 前缀也接受）：

```shell
curl --request POST \
  --url http://localhost:8820/v1/audio/transcriptions \
  --header 'Authorization: Bearer sk-your-own-key' \
  --form model=Qwen3-ASR-1.7B \
  --form file='@audio.wav'
```

`REQUIRE_API_KEY` 可以在不删除 `API_KEY` 的前提下开关校验：

| `API_KEY` | `REQUIRE_API_KEY` | 结果 |
| --- | --- | --- |
| 未设置 | 未设置 | 不校验（默认） |
| 已设置 | 未设置 | 校验（等同旧行为） |
| 已设置 | `false` | 不校验，但密钥保留在环境里 |
| 已设置 | `true` | 校验 |
| 未设置 | `true` | 启动失败并报错（没有任何密钥能通过） |

> 密钥比较使用 `secrets.compare_digest`，为常数时间，避免逐字符比较带来的时序泄露。`OPTIONS` 预检请求不需要密钥，否则浏览器跨域会失败。

### 🌍 Language / 语言识别
模型自带语种识别，默认走 `auto`，无需指定语言。

客户端（如 Home Assistant）通常会按自己的配置固定发送一个 `language`，一旦有人说了别的语言就会出错，所以默认**忽略**客户端传来的 `language`。实测：中文音频若被强制指定 `language=en`，转写文本仍然是正确的中文，但返回的 `lang` 会被错标成 `English`；忽略之后 `lang` 恢复为 `Chinese`。

需要恢复旧行为（采纳客户端语言）时设 `TRUST_CLIENT_LANGUAGE=true`；想在服务端固定一个语种则用 `DEFAULT_LANGUAGE=zh`。

### 🔐 Qwen3-ASR-1.7B 创空间 / Studio endpoint
`https://qwen-qwen3-asr.ms.show` 需要携带 `studio_token` Cookie。只要配置对应模型的令牌即可，后端地址会自动指向该创空间：

```shell
docker run -d --name asr2api -p 8820:80 \
  -e qwen3-asr-1-7b-studio-token=your-token \
  ghcr.io/osscv/qwen-asr2api:main
```

> 上游镜像 `ghcr.nju.edu.cn/aahl/qwen-asr2api:main` 目前还没有这部分代码，令牌会被忽略；[PR #4](https://github.com/aahl/qwen-asr2api/pull/4) 合并后同样可用。

令牌键名按模型名归一化，下面几种写法等价，`_` 和 `-` 混用、大小写、`.` 或 `-` 分隔小版本号都能匹配到同一个模型：

```
qwen3-asr-1-7b-studio-token
QWEN3_ASR_1_7B_STUDIO_TOKEN
qwen3-asr-1.7b-hf-studio-token
```

请求时 `model` 也同样宽松：`Qwen3-ASR-1.7B`、`qwen3-asr-1-7b`、`qwen3-asr-1.7b-hf` 都会用上同一个令牌。

> 令牌只从环境变量读取，不写入代码，也不会出现在日志里。两个后端的接口形状不同（函数名、语言参数、返回顺序），程序会自动探测并适配。

### ⏱️ Word timestamps / 词级时间戳
studio 后端可返回词级时间戳，加上 `response_format=verbose_json` 或 `timestamp_granularities[]=word` 即可：

```shell
curl --request POST \
  --url http://localhost:8820/v1/audio/transcriptions \
  --form model=Qwen3-ASR-1.7B \
  --form response_format=verbose_json \
  --form file='@audio.wav'
```

响应会带上 `words` 数组，每项包含 `word`、`start`、`end`。


## 🔗 Links / 相关链接
- 默认转发目标：https://qwen-qwen3-asr-demo.ms.show
- Qwen3-ASR-1.7B 创空间：https://qwen-qwen3-asr.ms.show
- 说明：本项目当前是把远端 Gradio ASR Demo 包装成 OpenAI 风格接口，不是本地离线推理。
- https://linux.do/t/topic/1367480
