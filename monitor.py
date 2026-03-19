#!/usr/bin/env python3
"""
Website Uptime Monitor with Telegram Bot and Web Dashboard

環境變數設定:
- TELEGRAM_BOT_TOKEN: Telegram Bot Token
- TELEGRAM_CHAT_ID: Telegram Chat ID
- CHECK_INTERVAL: 檢查間隔（秒），預設 300
- TIMEOUT: 請求超時時間（秒），預設 10
- DB_PATH: SQLite 數據庫路徑，預設 /data/sites.db
"""

import os
import sys
import time
import logging
import asyncio
import threading
import json
import sqlite3
from datetime import datetime
from urllib.parse import urlparse, unquote
from typing import List, Dict, Optional
from contextlib import contextmanager

import aiohttp
import aiohttp.client_exceptions
from flask import Flask, jsonify, render_template_string, request

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
        
        /* Management styles */
        .manage-section {
            max-width: 800px; margin: 0 auto 2rem auto;
            background: #1e293b; border-radius: 12px; padding: 1.5rem;
        }
        .manage-section h2 {
            font-size: 1.2rem; color: #f8fafc; margin-bottom: 1rem;
            display: flex; align-items: center; gap: 0.5rem;
        }
        .add-site-form {
            display: flex; gap: 0.75rem; flex-wrap: wrap;
        }
        .add-site-form input {
            flex: 1; min-width: 250px;
            background: #0f172a; border: 1px solid #334155;
            border-radius: 8px; padding: 0.75rem 1rem;
            color: #e2e8f0; font-size: 0.95rem;
        }
        .add-site-form input:focus {
            outline: none; border-color: #60a5fa;
        }
        .btn {
            background: #3b82f6; color: white;
            border: none; border-radius: 8px;
            padding: 0.75rem 1.5rem; font-size: 0.95rem;
            font-weight: 600; cursor: pointer; transition: all 0.15s;
        }
        .btn:hover { background: #2563eb; }
        .btn-danger {
            background: #ef4444; padding: 0.5rem 1rem; font-size: 0.85rem;
        }
        .btn-danger:hover { background: #dc2626; }
        .btn-secondary {
            background: #64748b; padding: 0.5rem 1rem; font-size: 0.85rem;
        }
        .btn-secondary:hover { background: #475569; }
        .site-actions {
            display: flex; gap: 0.5rem; margin-left: 1rem;
        }
        .edit-form {
            display: flex; gap: 0.5rem; flex: 1;
        }
        .edit-form input {
            flex: 1;
            background: #0f172a; border: 1px solid #334155;
            border-radius: 6px; padding: 0.5rem 0.75rem;
            color: #e2e8f0; font-size: 0.9rem;
        }
        .message {
            padding: 0.75rem 1rem; border-radius: 8px;
            margin-bottom: 1rem; font-size: 0.9rem;
        }
        .message.success { background: #065f46; color: #6ee7b7; }
        .message.error { background: #7f1d1d; color: #fca5a5; }
        .hidden { display: none; }
        .tabs {
            display: flex; gap: 0.5rem; justify-content: center;
            margin-bottom: 2rem;
        }
        .tab {
            background: #1e293b; color: #94a3b8;
            border: none; border-radius: 8px;
            padding: 0.75rem 1.5rem; font-size: 0.95rem;
            cursor: pointer; transition: all 0.15s;
        }
        .tab.active { background: #3b82f6; color: white; }
        .tab:hover:not(.active) { background: #334155; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .storage-info {
            background: #1e293b; border-radius: 12px; padding: 1rem 1.5rem;
            margin-bottom: 1.5rem; font-size: 0.9rem; color: #94a3b8;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Website Monitor</h1>
        <p id="update-time">Loading...</p>
    </div>
    
    <div class="tabs">
        <button class="tab active" onclick="switchTab('dashboard')">📊 Dashboard</button>
        <button class="tab" onclick="switchTab('manage')">⚙️ Manage Sites</button>
    </div>
    
    <div id="dashboard" class="tab-content active">
        <div class="stats" id="stats"></div>
        <div class="sites" id="sites"></div>
        <div class="refresh-info">Auto-refresh every 30 seconds</div>
    </div>
    
    <div id="manage" class="tab-content">
        <div class="storage-info">
            💾 資料儲存在 SQLite 數據庫，已配置 Persistent Storage，重新部署不會遺失。
        </div>
        
        <div class="manage-section">
            <h2>➕ Add New Site</h2>
            <div id="add-message"></div>
            <form class="add-site-form" onsubmit="addSite(event)">
                <input type="url" id="new-site-url" placeholder="https://example.com" required>
                <button type="submit" class="btn">Add Site</button>
            </form>
        </div>
        
        <div class="manage-section">
            <h2>📋 Manage Sites</h2>
            <div id="manage-message"></div>
            <div id="sites-list"></div>
        </div>
    </div>
    
    <script>
        let editingSite = null;
        
        function switchTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelector(`.tab[onclick="switchTab('${tab}')"]`).classList.add('active');
            document.getElementById(tab).classList.add('active');
            if (tab === 'manage') loadSitesList();
        }
        
        function showMessage(elementId, text, isError = false) {
            const el = document.getElementById(elementId);
            el.className = `message ${isError ? 'error' : 'success'}`;
            el.textContent = text;
            setTimeout(() => el.className = 'hidden', 3000);
        }
        
        async function addSite(e) {
            e.preventDefault();
            const url = document.getElementById('new-site-url').value.trim();
            try {
                const res = await fetch('/api/sites', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url })
                });
                const data = await res.json();
                if (res.ok) {
                    showMessage('add-message', 'Site added successfully!');
                    document.getElementById('new-site-url').value = '';
                    loadSitesList();
                } else {
                    showMessage('add-message', data.error || 'Failed to add site', true);
                }
            } catch (e) {
                showMessage('add-message', 'Network error', true);
            }
        }
        
        async function loadSitesList() {
            try {
                const res = await fetch('/api/sites');
                const data = await res.json();
                const el = document.getElementById('sites-list');
                if (!data.sites || data.sites.length === 0) {
                    el.innerHTML = '<div class="no-data">No sites configured</div>';
                    return;
                }
                el.innerHTML = data.sites.map(site => `
                    <div class="site-card" id="site-${encodeURIComponent(site.url)}">
                        ${editingSite === site.url ? `
                            <form class="edit-form" onsubmit="updateSite(event, '${encodeURIComponent(site.url)}')">
                                <input type="url" id="edit-${encodeURIComponent(site.url)}" value="${site.url}" required>
                                <button type="submit" class="btn">Save</button>
                                <button type="button" class="btn btn-secondary" onclick="cancelEdit()">Cancel</button>
                            </form>
                        ` : `
                            <div class="site-info">
                                <div class="site-url">${site.url}</div>
                                <div class="site-meta">ID: ${site.id}</div>
                            </div>
                            <div class="site-actions">
                                <button class="btn btn-secondary" onclick="startEdit('${encodeURIComponent(site.url)}')">Edit</button>
                                <button class="btn btn-danger" onclick="deleteSite('${encodeURIComponent(site.url)}')">Delete</button>
                            </div>
                        `}
                    </div>
                `).join('');
            } catch (e) {
                document.getElementById('sites-list').innerHTML = '<div class="no-data">Failed to load sites</div>';
            }
        }
        
        function startEdit(urlEncoded) {
            editingSite = decodeURIComponent(urlEncoded);
            loadSitesList();
        }
        
        function cancelEdit() {
            editingSite = null;
            loadSitesList();
        }
        
        async function updateSite(e, oldUrlEncoded) {
            e.preventDefault();
            const oldUrl = decodeURIComponent(oldUrlEncoded);
            const newUrl = document.getElementById(`edit-${oldUrlEncoded}`).value.trim();
            try {
                const res = await fetch(`/api/sites/${oldUrlEncoded}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: newUrl })
                });
                const data = await res.json();
                if (res.ok) {
                    editingSite = null;
                    showMessage('manage-message', 'Site updated successfully!');
                    loadSitesList();
                } else {
                    showMessage('manage-message', data.error || 'Failed to update site', true);
                }
            } catch (e) {
                showMessage('manage-message', 'Network error', true);
            }
        }
        
        async function deleteSite(urlEncoded) {
            if (!confirm('Are you sure you want to delete this site?')) return;
            try {
                const res = await fetch(`/api/sites/${urlEncoded}`, { method: 'DELETE' });
                const data = await res.json();
                if (res.ok) {
                    showMessage('manage-message', 'Site deleted successfully!');
                    loadSitesList();
                } else {
                    showMessage('manage-message', data.error || 'Failed to delete site', true);
                }
            } catch (e) {
                showMessage('manage-message', 'Network error', true);
            }
        }
        
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


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()
    
    def _init_db(self):
        """初始化數據庫"""
        # 確保目錄存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with self._get_conn() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
    
    @contextmanager
    def _get_conn(self):
        """獲取數據庫連接"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def get_all_sites(self) -> List[Dict]:
        """獲取所有網站"""
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute('SELECT id, url FROM sites ORDER BY id')
                return [{'id': row['id'], 'url': row['url']} for row in cursor.fetchall()]
    
    def add_site(self, url: str) -> tuple[bool, str]:
        """添加網站"""
        with self._lock:
            try:
                with self._get_conn() as conn:
                    conn.execute('INSERT INTO sites (url) VALUES (?)', (url,))
                    conn.commit()
                return True, "Site added successfully"
            except sqlite3.IntegrityError:
                return False, "Site already exists"
            except Exception as e:
                return False, str(e)
    
    def update_site(self, old_url: str, new_url: str) -> tuple[bool, str]:
        """更新網站"""
        with self._lock:
            try:
                with self._get_conn() as conn:
                    # 檢查舊 URL 是否存在
                    cursor = conn.execute('SELECT id FROM sites WHERE url = ?', (old_url,))
                    if not cursor.fetchone():
                        return False, "Site not found"
                    
                    # 檢查新 URL 是否已存在
                    if old_url != new_url:
                        cursor = conn.execute('SELECT id FROM sites WHERE url = ?', (new_url,))
                        if cursor.fetchone():
                            return False, "New URL already exists"
                    
                    conn.execute('UPDATE sites SET url = ? WHERE url = ?', (new_url, old_url))
                    conn.commit()
                return True, "Site updated successfully"
            except Exception as e:
                return False, str(e)
    
    def delete_site(self, url: str) -> tuple[bool, str]:
        """刪除網站"""
        with self._lock:
            try:
                with self._get_conn() as conn:
                    cursor = conn.execute('DELETE FROM sites WHERE url = ?', (url,))
                    conn.commit()
                    if cursor.rowcount == 0:
                        return False, "Site not found"
                return True, "Site deleted successfully"
            except Exception as e:
                return False, str(e)


class WebsiteMonitor:
    def __init__(self):
        self.telegram_bot_token: Optional[str] = None
        self.telegram_chat_id: Optional[str] = None
        self.check_interval: int = 300
        self.timeout: int = 10
        self.db_path: str = os.getenv('DB_PATH', '/data/sites.db')
        self.status_history: Dict[str, Dict] = {}
        self.bot_loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.Lock()
        self.db: Database = Database(self.db_path)
        self.load_config()

    def load_config(self) -> None:
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')

        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.warning("Telegram not configured, notifications disabled")

        try:
            self.check_interval = int(os.getenv('CHECK_INTERVAL', '300'))
            self.timeout = int(os.getenv('TIMEOUT', '10'))
        except ValueError:
            logger.warning("Invalid interval/timeout, using defaults")
        
        sites = self.db.get_all_sites()
        logger.info(f"Loaded {len(sites)} sites from database")

    def get_sites(self) -> List[str]:
        """獲取所有網站 URL"""
        return [site['url'] for site in self.db.get_all_sites()]
    
    def get_sites_with_id(self) -> List[Dict]:
        """獲取所有網站（含 ID）"""
        return self.db.get_all_sites()

    def add_site(self, url: str) -> tuple[bool, str]:
        """添加網站"""
        url = url.strip()
        if not url:
            return False, "URL cannot be empty"
        if not url.startswith(('http://', 'https://')):
            return False, "URL must start with http:// or https://"
        
        success, message = self.db.add_site(url)
        if success:
            logger.info(f"Added site: {url}")
        return success, message

    def update_site(self, old_url: str, new_url: str) -> tuple[bool, str]:
        """更新網站"""
        new_url = new_url.strip()
        if not new_url:
            return False, "URL cannot be empty"
        if not new_url.startswith(('http://', 'https://')):
            return False, "URL must start with http:// or https://"
        
        success, message = self.db.update_site(old_url, new_url)
        if success:
            logger.info(f"Updated site: {old_url} -> {new_url}")
            # 更新狀態歷史
            if old_url in self.status_history:
                self.status_history[new_url] = self.status_history.pop(old_url)
                self.status_history[new_url]['url'] = new_url
        return success, message

    def delete_site(self, url: str) -> tuple[bool, str]:
        """刪除網站"""
        success, message = self.db.delete_site(url)
        if success:
            logger.info(f"Deleted site: {url}")
            if url in self.status_history:
                del self.status_history[url]
        return success, message

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
        urls = self.get_sites()
        if not urls:
            return
            
        tasks = [self.check_website(url) for url in urls]
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
            sites = self.get_sites()
            if self.telegram_bot_token and self.telegram_chat_id:
                await self.send_telegram_message(
                    f"🚀 <b>Monitor Started</b>\n\n"
                    f"📋 Monitoring {len(sites)} sites\n"
                    f"⏱️ Interval: {self.check_interval}s\n\n"
                    f"💡 Send /status to check anytime"
                )

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
            'total': len(self.get_sites()),
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


@app.route('/api/sites', methods=['GET'])
def get_sites():
    """獲取所有網站"""
    if not monitor_instance:
        return jsonify({'error': 'Monitor not initialized'}), 500
    sites = monitor_instance.get_sites_with_id()
    return jsonify({'sites': sites})


@app.route('/api/sites', methods=['POST'])
def add_site():
    """添加網站"""
    if not monitor_instance:
        return jsonify({'error': 'Monitor not initialized'}), 500
    
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'URL is required'}), 400
    
    success, message = monitor_instance.add_site(data['url'])
    if success:
        return jsonify({'message': message})
    return jsonify({'error': message}), 400


@app.route('/api/sites/<path:url>', methods=['PUT'])
def update_site(url):
    """更新網站"""
    if not monitor_instance:
        return jsonify({'error': 'Monitor not initialized'}), 500
    
    old_url = unquote(url)
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'New URL is required'}), 400
    
    success, message = monitor_instance.update_site(old_url, data['url'])
    if success:
        return jsonify({'message': message})
    return jsonify({'error': message}), 400


@app.route('/api/sites/<path:url>', methods=['DELETE'])
def delete_site(url):
    """刪除網站"""
    if not monitor_instance:
        return jsonify({'error': 'Monitor not initialized'}), 500
    
    url = unquote(url)
    success, message = monitor_instance.delete_site(url)
    if success:
        return jsonify({'message': message})
    return jsonify({'error': message}), 404


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
