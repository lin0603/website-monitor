# 🌐 Website Monitor

輕量級網站監測工具，自動檢測網站狀態並透過 Telegram 發送異常通知。

## ✨ 功能特色

- 🔄 自動定期檢測網站狀態
- 📱 Telegram 即時通知
- ⚡ 異常恢復時也會通知
- 📝 支援同時監測多個網站
- 🐍 純 Python 實現，輕量快速
- 🐳 支援 Docker 部署

## 📁 檔案結構

```
website-monitor/
├── monitor.py          # 主要監測腳本
├── requirements.txt    # Python 依賴
├── .env.example        # 環境變數範本
├── .env                # 實際設定（需自行建立）
├── monitor.log         # 執行日誌
└── README.md           # 說明文件
```

## 🚀 快速開始

### 1. 安裝依賴

```bash
cd ~/lgndata/website-monitor
pip install -r requirements.txt
```

### 2. 設定環境變數

```bash
cp .env.example .env
# 編輯 .env 填入你的設定
```

### 3. 取得 Telegram Bot Token

1. 在 Telegram 搜尋 `@BotFather`
2. 發送 `/newbot` 建立新 Bot
3. 取得 Bot Token (格式: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
4. 搜尋 `@userinfobot` 取得你的 Chat ID

### 4. 執行監測器

```bash
# 持續監測模式
python monitor.py

# 單次測試模式
python monitor.py --once
```

## 🔧 環境變數說明

| 變數名稱 | 必填 | 預設值 | 說明 |
|---------|------|--------|------|
| `MONITOR_URLS` | ✅ | - | 要監測的網址，逗號分隔 |
| `TELEGRAM_BOT_TOKEN` | ✅ | - | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | ✅ | - | Telegram Chat ID |
| `CHECK_INTERVAL` | ❌ | 60 | 檢查間隔（秒） |
| `TIMEOUT` | ❌ | 10 | 請求超時（秒） |

## 🐳 Docker 部署

### 使用 Docker Run

```bash
docker run -d \
  --name website-monitor \
  -e MONITOR_URLS="https://example.com,https://google.com" \
  -e TELEGRAM_BOT_TOKEN="your_token" \
  -e TELEGRAM_CHAT_ID="your_chat_id" \
  -e CHECK_INTERVAL=60 \
  -v $(pwd)/monitor.log:/app/monitor.log \
  python:3.11-slim \
  bash -c "pip install aiohttp python-dotenv && python -c '\
import asyncio
import sys
sys.path.insert(0, \"/app\")
exec(open(\"/app/monitor.py\").read())
'"
```

### 使用 Docker Compose

建立 `docker-compose.yml`:

```yaml
version: '3.8'

services:
  monitor:
    build: .
    container_name: website-monitor
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./monitor.log:/app/monitor.log
```

建立 `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY monitor.py .

CMD ["python", "monitor.py"]
```

啟動服務:

```bash
docker-compose up -d
```

## 🔄 使用 Systemd 常駐執行（Linux）

建立服務檔案 `/etc/systemd/system/website-monitor.service`:

```ini
[Unit]
Description=Website Monitor
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/lgndata/website-monitor
EnvironmentFile=/home/your_username/lgndata/website-monitor/.env
ExecStart=/usr/bin/python3 /home/your_username/lgndata/website-monitor/monitor.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

啟用並啟動服務:

```bash
sudo systemctl daemon-reload
sudo systemctl enable website-monitor
sudo systemctl start website-monitor
sudo systemctl status website-monitor
```

## 📝 日誌查看

```bash
# 即時查看日誌
tail -f monitor.log

# 查看 Systemd 日誌
sudo journalctl -u website-monitor -f
```

## 🔍 類似專案參考

- [Uptime Kuma](https://github.com/louislam/uptime-kuma) - 功能完整的自托管監測工具
- [n8n Website Monitor](https://n8n.io/workflows/11763-website-downtime-monitoring-with-smart-alerts-via-telegram-and-email/) - 使用 n8n 工作流監測

## 📄 License

MIT License
