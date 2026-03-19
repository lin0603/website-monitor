#!/usr/bin/env python3
"""
Website Uptime Monitor with Telegram Bot and Web Dashboard

環境變數設定:
- MONITOR_URLS: 要監測的網址，以逗號分隔
- TELEGRAM_BOT_TOKEN: Telegram Bot Token
- TELEGRAM_CHAT_ID: Telegram Chat ID
- CHECK_INTERVAL: 檢查間隔（秒），預設 300
- TIMEOUT: 請求超時時間（秒），預設 10
"""

import os
import sys
import time
import logging
import asyncio
import threading
from datetime import datetime
from urllib.parse import urlparse
from typing import List, Dict, Optional

import aiohttp
import aiohttp.client_exceptions
from flask import Flask, jsonify, render_template_string

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
monitor_instance = None

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Website Monitor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
            padding: 2rem;
        }
        .header { text-align: center; margin-bottom: 2rem; }
        .header h1 { font-size: 1.8rem; color: #f8fafc; margin-bottom: 0.5rem; }
        .header p { color: #94a3b8; font-size: 0.9rem; }
        .stats {
            display: flex; gap: 1rem; justify-content: center;
            margin-bottom: 2rem; flex-wrap: wrap;
        }
        .stat-card {
            background: #1e293b; border-radius: 12px;
            padding: 1rem 1.5rem; text-align: center; min-width: 120px;
        }
        .stat-card .number { font-size: 2rem; font-weight: 700; }
        .stat-card .label { color: #94a3b8; font-size: 0.8rem; margin-top: 0.25rem; }
        .stat-card.up .number { color: #4ade80; }
        .stat-card.down .number { color: #f87171; }
        .stat-card.total .number { color: #60a5fa; }
        .sites {
            max-width: 800px; margin: 0 auto;
            display: flex; flex-direction: column; gap: 0.75rem;
        }
        .site-card {
            background: #1e293b; border-radius: 12px; padding: 1.25rem;
            display: flex; align-items: center; justify-content: space-between;
            border-left: 4px solid #475569; transition: transform 0.15s;
        }
        .site-card:hover { transform: translateX(4px); }
        .site-card.up { border-left-color: #4ade80; }
        .site-card.down { border-left-color: #f87171; }
        .site-card.error { border-left-color: #fbbf24; }
        .site-card.unknown { border-left-color: #475569; }
        .site-info { flex: 1; }
        .site-url { font-weight: 600; font-size: 1rem; color: #f1f5f9; word-break: break-all; }
        .site-meta { color: #94a3b8; font-size: 0.8rem; margin-top: 0.35rem; }
        .site-status { display: flex; align-items: center; gap: 0.75rem; }
        .response-time { color: #94a3b8; font-size: 0.85rem; }
        .badge {
            padding: 0.35rem 0.75rem; border-radius: 20px;
            font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
        }
        .badge.up { background: #065f46; color: #6ee7b7; }
        .badge.down { background: #7f1d1d; color: #fca5a5; }
        .badge.error { background: #78350f; color: #fde68a; }
        .badge.unknown { background: #334155; color: #94a3b8; }
        .error-msg { color: #f87171; font-size: 0.8rem; margin-top: 0.25rem; }
        .refresh-info { text-align: center; margin-top: 2rem; color: #475569; font-size: 0.8rem; }
        .no-data { text-align: center; color: #64748b; padding: 3rem; font-size: 1.1rem; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Website Monitor</h1>
        <p id="update-time">Loading...</p>
    </div>
    <div class="stats" id="stats"></div>
    <div class="sites" id="sites"></div>
    <div class="refresh-info">Auto-refresh every 30 seconds</div>
    <script>
        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                renderStats(data);
                renderSites(data.sites);
                document.getElementById('update-time').textContent =
                    'Last updated: ' + new Date().toLocaleTimeString();
            } catch (e) {
                document.getElementById('update-time').textContent = 'Connection error';
            }
        }
        function renderStats(data) {
            document.getElementById('stats').innerHTML = `
                <div class="stat-card total"><div class="number">${data.total}</div><div class="label">Total</div></div>
                <div class="stat-card up"><div class="number">${data.up}</div><div class="label">Online</div></div>
                <div class="stat-card down"><div class="number">${data.down}</div><div class="label">Offline</div></div>
            `;
        }
        function renderSites(sites) {
            const el = document.getElementById('sites');
            if (!sites || sites.length === 0) {
                el.innerHTML = '<div class="no-data">Waiting for first check...</div>';
                return;
            }
            el.innerHTML = sites.map(s => `
                <div class="site-card ${s.status}">
                    <div class="site-info">
                        <div class="site-url">${s.url}</div>
                        ${s.error ? `<div class="error-msg">${s.error}</div>` : ''}
                        <div class="site-meta">
                            ${s.status_code ? 'HTTP ' + s.status_code + ' · ' : ''}
                            ${s.timestamp || ''}
                        </div>
                    </div>
                    <div class="site-status">
                        <span class="response-time">${s.response_time} ms</span>
                        <span class="badge ${s.status}">${s.status}</span>
                    </div>
                </div>
            `).join('');
        }
        fetchStatus();
        setInterval(fetchStatus, 30000);
    </script>
</body>
</html>
"""


class WebsiteMonitor:
    def __init__(self):
        self.urls: List[str] = []
        self.telegram_bot_token: Optional[str] = None
        self.telegram_chat_id: Optional[str] = None
        self.check_interval: int = 300
        self.timeout: int = 10
        self.status_history: Dict[str, Dict] = {}
        self.bot_loop: Optional[asyncio.AbstractEventLoop] = None
        self.load_config()

    def load_config(self) -> None:
        urls_env = os.getenv('MONITOR_URLS', '')
        if not urls_env:
            logger.error("MONITOR_URLS not set")
            sys.exit(1)

        self.urls = [url.strip() for url in urls_env.split(',') if url.strip()]
        if not self.urls:
            logger.error("No valid URLs")
            sys.exit(1)

        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')

        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.warning("Telegram not configured, notifications disabled")

        try:
            self.check_interval = int(os.getenv('CHECK_INTERVAL', '300'))
            self.timeout = int(os.getenv('TIMEOUT', '10'))
        except ValueError:
            logger.warning("Invalid interval/timeout, using defaults")

        logger.info(f"Monitoring {len(self.urls)} URLs, interval: {self.check_interval}s")

    async def send_telegram_message(self, message: str, chat_id: Optional[str] = None) -> bool:
        if not self.telegram_bot_token:
            return False
        target_chat_id = chat_id or self.telegram_chat_id
        if not target_chat_id:
            return False

        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        payload = {
            'chat_id': target_chat_id,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Telegram API error: {error_text}")
                        return False
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    async def check_website(self, url: str) -> Dict:
        start_time = time.time()
        result = {
            'url': url, 'status': 'unknown', 'status_code': None,
            'response_time': 0, 'error': None,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ssl=False, allow_redirects=True
                ) as response:
                    result['response_time'] = round((time.time() - start_time) * 1000, 2)
                    result['status_code'] = response.status
                    if 200 <= response.status < 400:
                        result['status'] = 'up'
                    else:
                        result['status'] = 'error'
                        result['error'] = f'HTTP {response.status}'
        except asyncio.TimeoutError:
            result['status'] = 'down'
            result['response_time'] = self.timeout * 1000
            result['error'] = 'Connection timeout'
        except aiohttp.client_exceptions.ClientConnectorError as e:
            result['status'] = 'down'
            result['error'] = f'Cannot connect: {str(e)}'
        except Exception as e:
            result['status'] = 'down'
            result['error'] = str(e)

        return result

    def format_status_report(self) -> str:
        """格式化完整狀態報告（給 Telegram /status 用）"""
        if not self.status_history:
            return "📋 尚未有檢查資料，請稍後再試。"

        sites = list(self.status_history.values())
        up_count = sum(1 for s in sites if s['status'] == 'up')
        total = len(sites)

        lines = [
            f"📊 <b>網站監控報告</b>",
            f"",
            f"✅ Online: {up_count} / {total}",
            f"",
        ]

        for s in sites:
            domain = urlparse(s['url']).netloc or s['url']
            if s['status'] == 'up':
                icon = "🟢"
                detail = f"{s['response_time']} ms"
            elif s['status'] == 'error':
                icon = "🟡"
                detail = s.get('error', 'Error')
            else:
                icon = "🔴"
                detail = s.get('error', 'Down')

            lines.append(f"{icon} <b>{domain}</b>")
            lines.append(f"    {detail} | {s.get('timestamp', '')}")
            lines.append("")

        lines.append(f"⏱️ Check interval: {self.check_interval}s")
        return "\n".join(lines)

    async def check_all_websites(self) -> None:
        tasks = [self.check_website(url) for url in self.urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Check exception: {result}")
                continue

            url = result['url']
            prev_status = self.status_history.get(url, {}).get('status')
            current_status = result['status']
            self.status_history[url] = result

            if prev_status and prev_status != current_status:
                if current_status == 'up':
                    domain = urlparse(url).netloc or url
                    msg = (
                        f"🟢 <b>Website Recovered</b>\n\n"
                        f"🔗 <b>Site:</b> {domain}\n"
                        f"⏱️ <b>Response:</b> {result['response_time']} ms\n"
                        f"🕐 <b>Time:</b> {result['timestamp']}"
                    )
                    await self.send_telegram_message(msg)
                    logger.info(f"[RECOVERED] {url} ({result['response_time']} ms)")
                else:
                    domain = urlparse(url).netloc or url
                    error_msg = result.get('error', 'Unknown error')
                    msg = (
                        f"🔴 <b>Website Down</b>\n\n"
                        f"🔗 <b>Site:</b> {domain}\n"
                        f"❌ <b>Error:</b> {error_msg}\n"
                        f"⏱️ <b>Response:</b> {result['response_time']} ms\n"
                        f"🕐 <b>Time:</b> {result['timestamp']}"
                    )
                    await self.send_telegram_message(msg)
                    logger.warning(f"[DOWN] {url}: {result.get('error')}")
            else:
                if current_status == 'up':
                    logger.info(f"[OK] {url} ({result['response_time']} ms)")
                else:
                    logger.warning(f"[WARN] {url}: {result.get('error')}")

    async def handle_telegram_command(self, message: dict) -> None:
        """處理 Telegram Bot 收到的指令"""
        text = message.get('text', '').strip()
        chat_id = str(message['chat']['id'])

        if text == '/status':
            # 先即時檢查一次
            await self.check_all_websites()
            report = self.format_status_report()
            await self.send_telegram_message(report, chat_id=chat_id)

        elif text == '/check':
            await self.send_telegram_message("🔍 正在檢查中...", chat_id=chat_id)
            await self.check_all_websites()
            report = self.format_status_report()
            await self.send_telegram_message(report, chat_id=chat_id)

        elif text == '/help' or text == '/start':
            help_msg = (
                "🤖 <b>Website Monitor Bot</b>\n\n"
                "可用指令：\n"
                "/status - 查看所有網站目前狀態\n"
                "/check - 立即檢查並回報\n"
                "/help - 顯示此說明"
            )
            await self.send_telegram_message(help_msg, chat_id=chat_id)

    async def poll_telegram(self) -> None:
        """輪詢 Telegram Bot 訊息"""
        if not self.telegram_bot_token:
            return

        logger.info("Telegram bot polling started")
        offset = 0
        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/getUpdates"

        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    params = {'offset': offset, 'timeout': 30}
                    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=35)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get('ok'):
                                for update in data.get('result', []):
                                    offset = update['update_id'] + 1
                                    msg = update.get('message')
                                    if msg and msg.get('text', '').startswith('/'):
                                        await self.handle_telegram_command(msg)
            except Exception as e:
                logger.error(f"Telegram poll error: {e}")
                await asyncio.sleep(5)

    def run_monitor_loop(self) -> None:
        """背景執行緒：監測 + Telegram Bot"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.bot_loop = loop

        async def _run():
            logger.info("Monitor started")
            if self.telegram_bot_token and self.telegram_chat_id:
                await self.send_telegram_message(
                    f"🚀 <b>Monitor Started</b>\n\n"
                    f"📋 Monitoring {len(self.urls)} sites\n"
                    f"⏱️ Interval: {self.check_interval}s\n\n"
                    f"💡 Send /status to check anytime"
                )

            # 同時跑監測迴圈和 Telegram Bot 輪詢
            async def monitor_loop():
                while True:
                    await self.check_all_websites()
                    await asyncio.sleep(self.check_interval)

            await asyncio.gather(monitor_loop(), self.poll_telegram())

        loop.run_until_complete(_run())

    def get_status(self) -> Dict:
        sites = list(self.status_history.values())
        up_count = sum(1 for s in sites if s['status'] == 'up')
        down_count = sum(1 for s in sites if s['status'] != 'up')
        return {
            'total': len(self.urls),
            'up': up_count,
            'down': down_count,
            'sites': sites
        }


@app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML)


@app.route('/api/status')
def api_status():
    if monitor_instance:
        return jsonify(monitor_instance.get_status())
    return jsonify({'total': 0, 'up': 0, 'down': 0, 'sites': []})


def main():
    global monitor_instance
    monitor_instance = WebsiteMonitor()

    monitor_thread = threading.Thread(target=monitor_instance.run_monitor_loop, daemon=True)
    monitor_thread.start()

    port = int(os.getenv('PORT', '80'))
    logger.info(f"Dashboard running on port {port}")
    app.run(host='0.0.0.0', port=port)


if __name__ == '__main__':
    main()
