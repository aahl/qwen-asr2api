# 🎤 Qwen3 ASR

## Install / 安装

### 🐳 Docker compose
```shell
mkdir /opt/asr2api
cd /opt/asr2api
wget https://raw.githubusercontent.com/aahl/qwen-asr2api/refs/heads/main/docker-compose.yml
docker compose up -d
```


## 💻 Usage / 使用

```shell
curl --request POST \
  --url http://localhost:8820/v1/audio/transcriptions \
  --header 'Content-Type: multipart/form-data' \
  --form model=qwen3-asr-flash \
  --form file='@audio.wav'
```

### 模型列表
- `qwen3-asr-flash`
- `qwen-qwen3-asr:itn` 启用逆文本标准化（ITN）


## 🔗 Links / 相关链接
- https://qwen-qwen3-asr-demo.ms.show
