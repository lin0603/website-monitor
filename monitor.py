#!/usr/bin/env python3
"""
Website Uptime Monitor with Telegram Notifications
自動監測網站狀態並透過 Telegram 發送通知

環境變數設定:
- MONITOR_URLS: 要監測的網址，以逗號分隔 (e.g., "https://google.com,https://example.com")
- TELEGRAM_BOT_TOKEN: Telegram Bot Token
- TELEGRAM_CHAT_ID: Telegram Chat ID
- CHECK_INTERVAL: 檢查間隔（秒），預設 60
- TIMEOUT: 請求超時時間（秒），預設 10
"""

import os
import sys
import time
import json
import logging
import asyncio
from datetime import datetime
from urllib.parse import urlparse
from typing import List, Dict, Optional

import aiohttp
import aiohttp.client_exceptions


# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('monitor.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class WebsiteMonitor:
    """網站監測器"""
    
    def __init__(self):
        self.urls: List[str] = []
        self.telegram_bot_token: Optional[str] = None
        self.telegram_chat_id: Optional[str] = None
        self.check_interval: int = 60
        self.timeout: int = 10
        self.status_history: Dict[str, Dict] = {}
        self.load_config()
        
    def load_config(self) -> None:
        """從環境變數載入設定"""
        # 載入要監測的網址
        urls_env = os.getenv('MONITOR_URLS', '')
        if not urls_env:
            logger.error("❌ 環境變數 MONITOR_URLS 未設定")
            sys.exit(1)
        
        self.urls = [url.strip() for url in urls_env.split(',') if url.strip()]
        if not self.urls:
            logger.error("❌ 沒有有效的網址可監測")
            sys.exit(1)
            
        # Telegram 設定
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.warning("⚠️ Telegram 設定不完整，將不會發送通知")
        
        # 其他設定
        try:
            self.check_interval = int(os.getenv('CHECK_INTERVAL', '60'))
            self.timeout = int(os.getenv('TIMEOUT', '10'))
        except ValueError:
            logger.warning("⚠️ 間隔或超時設定無效，使用預設值")
            
        logger.info(f"✅ 已載入 {len(self.urls)} 個監測目標")
        logger.info(f"⏱️  檢查間隔: {self.check_interval} 秒")
        
    async def send_telegram_message(self, message: str) -> bool:
        """發送 Telegram 訊息"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return False
            
        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        payload = {
            'chat_id': self.telegram_chat_id,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        logger.info("📨 Telegram 訊息已發送")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Telegram API 錯誤: {error_text}")
                        return False
        except Exception as e:
            logger.error(f"❌ 發送 Telegram 訊息失敗: {e}")
            return False
            
    async def check_website(self, url: str) -> Dict:
        """檢查網站狀態"""
        start_time = time.time()
        result = {
            'url': url,
            'status': 'unknown',
            'status_code': None,
            'response_time': 0,
            'error': None,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, 
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ssl=False,  # 允許自簽憑證
                    allow_redirects=True
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
            result['error'] = '連線超時'
        except aiohttp.client_exceptions.ClientConnectorError as e:
            result['status'] = 'down'
            result['error'] = f'無法連線: {str(e)}'
        except Exception as e:
            result['status'] = 'down'
            result['error'] = str(e)
            
        return result
        
    def format_alert_message(self, result: Dict, is_recovery: bool = False) -> str:
        """格式化警報訊息"""
        url = result['url']
        domain = urlparse(url).netloc or url
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if is_recovery:
            return f"""🟢 <b>網站恢復正常</b>

🔗 <b>網站:</b> {domain}
⏱️ <b>回應時間:</b> {result['response_time']} ms
🕐 <b>時間:</b> {timestamp}"""
        else:
            error_msg = result.get('error', '未知錯誤')
            return f"""🔴 <b>網站異常警告</b>

🔗 <b>網站:</b> {domain}
❌ <b>錯誤:</b> {error_msg}
⏱️ <b>回應時間:</b> {result['response_time']} ms
🕐 <b>時間:</b> {timestamp}"""
            
    async def check_all_websites(self) -> None:
        """檢查所有網站"""
        tasks = [self.check_website(url) for url in self.urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"❌ 檢查時發生例外: {result}")
                continue
                
            url = result['url']
            prev_status = self.status_history.get(url, {}).get('status')
            current_status = result['status']
            
            # 記錄狀態
            self.status_history[url] = result
            
            # 狀態變化時發送通知
            if prev_status and prev_status != current_status:
                if current_status == 'up':
                    # 從異常恢復
                    message = self.format_alert_message(result, is_recovery=True)
                    await self.send_telegram_message(message)
                    logger.info(f"🟢 {url} 已恢復正常 ({result['response_time']} ms)")
                else:
                    # 發生異常
                    message = self.format_alert_message(result, is_recovery=False)
                    await self.send_telegram_message(message)
                    logger.warning(f"🔴 {url} 異常: {result.get('error')}")
            else:
                # 記錄正常檢查結果
                if current_status == 'up':
                    logger.info(f"✅ {url} 正常 ({result['response_time']} ms)")
                else:
                    logger.warning(f"⚠️  {url} 異常: {result.get('error')}")
                    
    async def run(self) -> None:
        """持續執行監測"""
        logger.info("🚀 網站監測器已啟動")
        logger.info(f"📋 監測目標: {', '.join(self.urls)}")
        
        # 發送啟動通知
        if self.telegram_bot_token and self.telegram_chat_id:
            await self.send_telegram_message(
                f"🚀 <b>監測器已啟動</b>\n\n"
                f"📋 監測 {len(self.urls)} 個網站\n"
                f"⏱️ 檢查間隔: {self.check_interval} 秒"
            )
        
        try:
            while True:
                await self.check_all_websites()
                await asyncio.sleep(self.check_interval)
        except KeyboardInterrupt:
            logger.info("🛑 監測器已停止")
            if self.telegram_bot_token and self.telegram_chat_id:
                await self.send_telegram_message("🛑 <b>監測器已停止</b>")
                
    async def run_once(self) -> None:
        """執行一次檢查（用於測試）"""
        logger.info("🔍 執行單次檢查...")
        await self.check_all_websites()


def main():
    """主程式"""
    monitor = WebsiteMonitor()
    
    # 檢查是否有 --once 參數
    if '--once' in sys.argv:
        asyncio.run(monitor.run_once())
    else:
        asyncio.run(monitor.run())


if __name__ == '__main__':
    main()
