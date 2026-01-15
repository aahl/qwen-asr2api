# 🎤 Qwen ASR

## Install / 安装

### 🐳 Docker compose
```shell
mkdir /opt/asr2api
cd /opt/asr2api
wget https://raw.githubusercontent.com/aahl/qwen-asr2api/refs/heads/main/docker-compose.yml
docker compose up -d
```

### 🐳 Docker run
```shell
docker run -d \
  --name asr2api \
  --restart=unless-stopped \
  -p 8820:80 \
  ghcr.nju.edu.cn/aahl/qwen-asr2api:main
```

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
  --header 'Content-Type: multipart/form-data' \
  --form model=qwen3-asr \
  --form file='@audio.wav'
```

### 🏠 Home Assistant
1. 安装 AI Conversation 集成
   > 点击这里 [一键安装](https://my.home-assistant.io/redirect/hacs_repository/?category=integration&owner=hasscc&repository=ai-conversation)，安装完记得重启HA
2. [添加 AI Conversation 服务](https://my.home-assistant.io/redirect/config_flow_start/?domain=ai_conversation)，配置模型提供商
   > 服务商: 自定义; 接口: `http://4e0de88e-qwen-asr/v1`; 密钥留空
3. 添加STT模型
4. 配置语音助手

## 🤖 Models / 模型
- `qwen3-asr`
- `qwen3-asr:itn` 启用逆文本标准化


## 🔗 Links / 相关链接
- https://qwen-qwen3-asr-demo.ms.show
- https://linux.do/t/topic/1367480
