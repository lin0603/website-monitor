# Website Monitor - 部署與維運記錄

## 專案概述
網站運行狀態監控器，具備 Web Dashboard 和 Telegram Bot 功能，支援網頁端增刪改監控網站。

## GCP VM 資訊
- **Instance**: `instance-20260319-020944`
- **Zone**: `us-west1-a`
- **Machine Type**: `e2-micro` (2 vCPU, 1 GB RAM)
- **OS**: Ubuntu 22.04 Minimal
- **Internal IP**: `10.138.0.2`
- **External IP**: `35.212.199.115`
- **Disk**: 30 GB Standard Persistent Disk

## SSH 連線方式
```bash
ssh -i ~/.ssh/gcp_vm lin0603@35.212.199.115
```
- SSH Key: `~/.ssh/gcp_vm` (ed25519)
- Public Key 已加入 GCP VM 的安全殼層金鑰

## VM 初始設定
### 1. Swap (4GB)
```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 2. Docker (降級至 25.0.5，相容 CapRover)
```bash
curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh
# 降級 Docker 以相容 CapRover (API version 1.44)
sudo apt-get install -y --allow-downgrades \
  docker-ce=5:25.0.5-1~ubuntu.22.04~jammy \
  docker-ce-cli=5:25.0.5-1~ubuntu.22.04~jammy
```
> **注意**: CapRover latest image 內建 dockerode client 版本 1.44，
> Docker 29.x (API 1.54, min 1.40) 會報 "client version 1.38 is too old"，
> Docker 24.x (API 1.43) 會報 "client version 1.44 is too new"，
> Docker 25.x (API 1.44) 剛好匹配。

### 3. CapRover 安裝
```bash
# 不要預先 docker swarm init，讓 CapRover 自己初始化
sudo docker run -d -p 80:80 -p 443:443 -p 3000:3000 \
  -e ACCEPTED_TERMS=true \
  -e BY_PASS_PROXY_CHECK=TRUE \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /captain:/captain \
  caprover/caprover
```

## CapRover 設定
- **Dashboard**: https://captain.gcp-caprover.starxinteractive.com
- **密碼**: `captainlin19790603`

## DNS 設定 (Cloudflare)
域名: `starxinteractive.com`

| Type | Name | Value | Proxy |
|------|------|-------|-------|
| A | `*.gcp-caprover` | `35.212.199.115` | DNS only (灰色雲朵) |
| A | `gcp-caprover` | `35.212.199.115` | DNS only (灰色雲朵) |

## GCP 防火牆規則
需手動建立 VPC 防火牆規則（不是在 Network Policy 裡面）：
- **名稱**: `allow-caprover`
- **目標**: 網路中的所有執行個體
- **來源 IPv4**: `0.0.0.0/0`
- **TCP Ports**: `80,443,3000`

## 部署方式 — CapRover Tar Upload API

### 方式說明
不使用 git push 部署，而是透過 CapRover REST API 直接上傳 tar 檔案部署。
流程：本機打包 tar → 透過 HTTP POST 上傳到 CapRover API → CapRover 自動 build Docker image 並部署。

### 步驟 1：登入取得 Token
```bash
curl -s -X POST https://captain.gcp-caprover.starxinteractive.com/api/v2/login \
  -H "Content-Type: application/json" \
  -d '{"password":"captainlin19790603"}'
```
回傳：
```json
{"status":100,"description":"Login succeeded","data":{"token":"<JWT_TOKEN>"}}
```

### 步驟 2：建立 App（只需首次）
```bash
TOKEN="<JWT_TOKEN>"
curl -s -X POST https://captain.gcp-caprover.starxinteractive.com/api/v2/user/apps/appDefinitions/register \
  -H "Content-Type: application/json" \
  -H "x-captain-auth: $TOKEN" \
  -d '{"appName":"website-monitor","hasPersistentData":true}'
```

### 步驟 3：設定環境變數、Persistent Storage
```bash
curl -s -X POST https://captain.gcp-caprover.starxinteractive.com/api/v2/user/apps/appDefinitions/update \
  -H "Content-Type: application/json" \
  -H "x-captain-auth: $TOKEN" \
  -d '{
    "appName": "website-monitor",
    "instanceCount": 1,
    "envVars": [
      {"key": "TELEGRAM_BOT_TOKEN", "value": "8600611014:AAH-lBBebmts-2XNZrnjjQWkz1B39IDYr1U"},
      {"key": "TELEGRAM_CHAT_ID", "value": "5032663412"},
      {"key": "CHECK_INTERVAL", "value": "300"},
      {"key": "DB_PATH", "value": "/data/sites.db"}
    ],
    "containerHttpPort": 80,
    "hasPersistentData": true,
    "volumes": [
      {
        "containerPath": "/data",
        "hostPath": "/captain/data/monitor"
      }
    ]
  }'
```
> **重要**: 更新時必須帶上所有欄位（envVars + instanceCount），否則未帶的欄位會被清空。

### 步驟 4：建立 Persistent 目錄（只需首次）
```bash
ssh -i ~/.ssh/gcp_vm lin0603@35.212.199.115 \
  "sudo mkdir -p /captain/data/monitor && sudo chmod 777 /captain/data/monitor"
```

### 步驟 5：打包並上傳部署
```bash
# 在專案目錄下打包（必須包含 captain-definition）
tar -cf /tmp/website-monitor.tar captain-definition Dockerfile monitor.py requirements.txt

# 上傳部署
curl -s -X POST https://captain.gcp-caprover.starxinteractive.com/api/v2/user/apps/appData/website-monitor \
  -H "x-captain-auth: $TOKEN" \
  -F "sourceFile=@/tmp/website-monitor.tar"
```
回傳：
```json
{"status":100,"description":"Deploy is done","data":{}}
```

### 步驟 6：驗證
```bash
# 檢查 HTTP 狀態
curl -s -o /dev/null -w "%{http_code}" http://website-monitor.gcp-caprover.starxinteractive.com

# 檢查 VM 上的 service 狀態
ssh -i ~/.ssh/gcp_vm lin0603@35.212.199.115 "sudo docker service ls | grep monitor"

# 查看 log
ssh -i ~/.ssh/gcp_vm lin0603@35.212.199.115 "sudo docker service logs srv-captain--website-monitor --tail 20"
```

## 環境變數
| Key | Value | 說明 |
|-----|-------|------|
| `TELEGRAM_BOT_TOKEN` | `8600611014:AAH-lBBebmts-2XNZrnjjQWkz1B39IDYr1U` | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | `5032663412` | Telegram Chat ID |
| `CHECK_INTERVAL` | `300` | 檢查間隔（秒），預設 5 分鐘 |
| `DB_PATH` | `/data/sites.db` | SQLite 數據庫路徑 |

## Persistent Data 配置

使用 **Bind Mount** 方式將容器內的 `/data` 掛載到主機的 `/captain/data/monitor`：

- **主機路徑**: `/captain/data/monitor`
- **容器路徑**: `/data`
- **用途**: 儲存 SQLite 數據庫 (`sites.db`)
- **特點**: 重新部署後資料不會遺失

檢查資料是否正確儲存：
```bash
ssh -i ~/.ssh/gcp_vm lin0603@35.212.199.115 \
  "sudo ls -la /captain/data/monitor/"
```

## 網頁管理功能

### Dashboard 標籤頁
- 即時顯示所有網站狀態（Online/Offline）
- 自動每 30 秒刷新
- 顯示 HTTP 狀態碼和響應時間

### Manage Sites 標籤頁
- **Add Site**: 添加新網站
- **Edit**: 修改網址
- **Delete**: 刪除網站

### REST API
| 方法 | 端點 | 功能 |
|------|------|------|
| GET | `/api/sites` | 獲取所有網站 |
| POST | `/api/sites` | 添加網站 |
| PUT | `/api/sites/<url>` | 更新網站 |
| DELETE | `/api/sites/<url>` | 刪除網站 |
| GET | `/api/status` | 獲取監控狀態 |

## Telegram Bot 指令
| 指令 | 功能 |
|------|------|
| `/status` | 查看所有網站目前狀態 |
| `/check` | 立即檢查並回報 |
| `/help` | 顯示指令說明 |

## 服務 URL
- **Web Dashboard**: http://website-monitor.gcp-caprover.starxinteractive.com
- **CapRover 管理**: https://captain.gcp-caprover.starxinteractive.com

## 費用評估
GCP Free Tier 完全覆蓋，一整年不會收費：
- e2-micro: 每月 1 台免費（限 us-west1 等區域）
- 30 GB 標準磁碟: 免費
- 出站流量: 每月 < 100 MB（免費額度 1 GB）
- 外部 IP: 附加到運行中 VM 免費

---

## 更新記錄

### 2026-03-19 - SQLite + Persistent Storage
- ✅ 改用 SQLite 數據庫 (`sites.db`) 儲存網站列表
- ✅ 配置 Bind Mount Persistent Storage (`/captain/data/monitor` → `/data`)
- ✅ 網頁增刪改功能完善，重新部署資料不遺失
- ✅ 更新部署文檔

### 2026-03-19 - 網頁管理功能
- ✅ 新增網站列表的增刪改功能（透過 Web Dashboard）
- ✅ 新增 REST API: `GET/POST/PUT/DELETE /api/sites`
- ✅ 配置 CapRover Persistent Directory

**訪問地址**: http://website-monitor.gcp-caprover.starxinteractive.com
