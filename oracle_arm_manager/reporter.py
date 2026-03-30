import os
import json
import subprocess
from datetime import datetime, timedelta
from typing import Optional

from oracle_arm_manager.logger import logger
from oracle_arm_manager.notifier import send_notification

def get_run_count(repo: str, workflow: str, since: str, status: Optional[str] = None) -> int:
    """透過 gh CLI 取得指定 workflow 過去 24 小時的執行次數"""
    cmd = [
        "gh", "run", "list",
        "--repo", repo,
        "--workflow", workflow,
        "--limit", "100",
        "--json", "createdAt"
    ]
    if status:
        cmd.extend(["--status", status])
        
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        runs = json.loads(res.stdout)
        
        # 計算時間大於 since 的數量
        count = sum(1 for r in runs if r.get("createdAt", "") > since)
        return count
    except subprocess.CalledProcessError as e:
        logger.error("gh CLI 取回執行資料失敗: %s\n%s", e, e.stderr)
        return 0
    except json.JSONDecodeError as e:
        logger.error("gh CLI 回傳了非 JSON 的資料: %s", e)
        return 0
    except Exception as e:
        logger.error("取得 %s 執行次數發生未知名錯誤: %s", workflow, str(e), exc_info=True)
        return 0

def build_daily_report() -> Optional[str]:
    repo = os.getenv("GITHUB_REPOSITORY")
    
    if not repo:
        logger.error("缺少 GITHUB_REPOSITORY 環境變數，無法執行")
        return None

    # 取得 24 小時前的 ISO 8601 時間字串 (UTC)
    since_dt = datetime.utcnow() - timedelta(hours=24)
    since_str = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    logger.info("開始生成每日報表，統計區間起自: %s", since_str)

    fail_count = get_run_count(repo, "register.yml", since_str)
    run_count = get_run_count(repo, "daily_report.yml", since_str)
    notify_fail_count = get_run_count(repo, "daily_report.yml", since_str, status="failure")

    date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # 注意：notifier.py 中已經會加上 github 的環境資訊 (Run ID 等)
    msg = (
        f"📅 {date_str}\n\n"
        f"目前狀態：資源仍不足，持續嘗試中。\n"
        f"❌ 今日失敗嘗試：{fail_count} 次\n\n"
        f"📣 通知執行次數：{run_count} 次\n"
        f"⚠️ 通知失敗次數：{notify_fail_count} 次"
    )
    return msg

def send_daily_report() -> None:
    msg = build_daily_report()
    if msg:
        logger.info("===== 發送每日監控回報 =====\n%s", msg)
        send_notification("每日監控回報", msg, is_success=True)
