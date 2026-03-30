import os
import logging
from typing import Optional
import requests


class NotificationError(Exception):
    pass


def _get_github_info() -> str:
    workflow = os.getenv("GITHUB_WORKFLOW", "Unknown")
    run_id = os.getenv("GITHUB_RUN_ID", "N/A")
    return f"\n\n📌 GitHub Actions ({workflow})\n🔗 Run ID: {run_id}"


def _safe_post(url: str, json: dict, headers: Optional[dict] = None, timeout: int = 10) -> None:
    try:
        resp = requests.post(url, json=json, headers=headers or {}, timeout=timeout)
        resp.raise_for_status()
        logging.debug("通知成功: %s, status_code=%s", url, resp.status_code)
    except requests.RequestException as e:
        logging.error("通知發送失敗 %s: %s", url, e, exc_info=True)
        raise NotificationError(f"通知發送失敗 {url}: {e}") from e


def send_line_notification(title: str, content: str, is_success: bool = False) -> None:
    token = os.getenv("LINE_ACCESS_TOKEN")
    user_id = os.getenv("LINE_USER_ID")
    if not token or not user_id:
        logging.debug("LINE 憑證不存在，跳過 LINE 通知")
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
    _safe_post("https://api.line.me/v2/bot/message/push", payload, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})


def send_telegram_notification(title: str, content: str, is_success: bool = False) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logging.debug("Telegram 憑證不存在，跳過 Telegram 通知")
        return

    status_icon = "🟢" if is_success else "🔴"
    message = f"{status_icon} *{title}*\n\n{content}{_get_github_info()}"

    _safe_post(f"https://api.telegram.org/bot{token}/sendMessage", {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})


def send_discord_notification(title: str, content: str, is_success: bool = False) -> None:
    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        logging.debug("Discord webhook 不存在，跳過 Discord 通知")
        return

    color = 65280 if is_success else 16711680
    payload = {
        "embeds": [{
            "title": title,
            "description": content,
            "color": color,
            "footer": {"text": f"GitHub Actions | Run ID: {os.getenv('GITHUB_RUN_ID', 'N/A')}"}
        }]
    }
    _safe_post(webhook, payload)


def send_notification(title: str, content: str, is_success: bool = False) -> None:
    send_func = [send_line_notification, send_telegram_notification, send_discord_notification]
    errors = []
    for func in send_func:
        try:
            func(title, content, is_success=is_success)
        except NotificationError as err:
            errors.append(str(err))
    if errors:
        logging.warning("部分通知失敗：%s", "; ".join(errors))
