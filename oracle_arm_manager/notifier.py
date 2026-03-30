import os
from typing import Optional, Dict, Any, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry # type: ignore
from oracle_arm_manager.logger import logger

class NotificationError(Exception):
    """自訂通知發送錯誤"""
    pass

def _get_github_info() -> str:
    workflow = os.getenv("GITHUB_WORKFLOW", "Unknown")
    run_id = os.getenv("GITHUB_RUN_ID", "N/A")
    return f"\n\n📌 GitHub Actions ({workflow})\n🔗 Run ID: {run_id}"

class BaseNotifier:
    """通知基底類別"""
    def send(self, title: str, content: str, is_success: bool = False) -> None:
        raise NotImplementedError

    def _safe_post(self, url: str, json_data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, timeout: int = 15) -> None:
        session = requests.Session()
        # 設定重試策略：重試 3 次，指數退避，針對分佈在 500-504 的錯誤代碼進行重試
        retries = Retry(
            total=3, 
            backoff_factor=2, 
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=True
        )
        session.mount("https://", HTTPAdapter(max_retries=retries))
        session.mount("http://", HTTPAdapter(max_retries=retries))

        try:
            resp = session.post(url, json=json_data, headers=headers or {}, timeout=timeout)
            resp.raise_for_status()
            logger.debug("通知發送成功: %s, status_code=%s", url, resp.status_code)
        except requests.RequestException as e:
            err_msg = f"通知發送失敗 (已重試): {url}: {str(e)}"
            logger.error(err_msg, exc_info=True)
            raise NotificationError(err_msg) from e
        finally:
            session.close()

class LineNotifier(BaseNotifier):
    def send(self, title: str, content: str, is_success: bool = False) -> None:
        token = os.getenv("LINE_ACCESS_TOKEN")
        user_id = os.getenv("LINE_USER_ID")
        if not token or not user_id:
            logger.debug("跳過 LINE 通知: 尚未設定憑證")
            return

        color = "#00ff00" if is_success else "#ff0000"
        payload = {
            "to": user_id,
            "messages": [{
                "type": "flex",
                "altText": title,
                "contents": {
                    "type": "bubble",
                    "header": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": title, "weight": "bold", "color": color}]},
                    "body": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": content, "wrap": True, "size": "sm"}]},
                },
            }],
        }
        self._safe_post(
            "https://api.line.me/v2/bot/message/push", 
            payload, 
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )

class TelegramNotifier(BaseNotifier):
    def send(self, title: str, content: str, is_success: bool = False) -> None:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            logger.debug("跳過 Telegram 通知: 尚未設定憑證")
            return

        status_icon = "🟢" if is_success else "🔴"
        message = f"{status_icon} *{title}*\n\n{content}{_get_github_info()}"
        
        self._safe_post(
            f"https://api.telegram.org/bot{token}/sendMessage", 
            {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        )

class DiscordNotifier(BaseNotifier):
    def send(self, title: str, content: str, is_success: bool = False) -> None:
        webhook = os.getenv("DISCORD_WEBHOOK_URL")
        if not webhook:
            logger.debug("跳過 Discord 通知: 尚未設定 webhook")
            return

        color = 65280 if is_success else 16711680
        payload = {
            "embeds": [{
                "title": title,
                "description": f"{content}{_get_github_info()}",
                "color": color,
            }]
        }
        self._safe_post(webhook, payload)

class NotificationManager:
    """封裝所有通知管道發送邏輯"""
    def __init__(self) -> None:
        self.notifiers: List[BaseNotifier] = [
            LineNotifier(),
            TelegramNotifier(),
            DiscordNotifier()
        ]

    def notify_all(self, title: str, content: str, is_success: bool = False) -> None:
        errors: List[str] = []
        for notifier in self.notifiers:
            try:
                notifier.send(title, content, is_success)
            except NotificationError as err:
                errors.append(str(err))

        if errors:
            logger.warning("部份通知傳送失敗: %s", "; ".join(errors))

# 全域單例
notification_manager = NotificationManager()

def send_notification(title: str, content: str, is_success: bool = False) -> None:
    """為了相容現有腳本的快捷函數"""
    notification_manager.notify_all(title, content, is_success)
