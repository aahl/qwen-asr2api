# 🎤 Qwen3 ASR

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
[![添加加载项仓库](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgitee.com%2Fhasscc%2Faddons)


## 💻 Usage / 使用

```shell
curl --request POST \
  --url http://localhost:8820/v1/audio/transcriptions \
  --header 'Content-Type: multipart/form-data' \
  --form model=qwen3-asr-flash \
  --form file='@audio.wav'
```

### 🤖 模型列表
- `qwen3-asr`
- `qwen3-asr:itn` 启用逆文本标准化


## 🔗 Links / 相关链接
- https://qwen-qwen3-asr-demo.ms.show
