import os
import json
import subprocess
import re
from datetime import datetime, timedelta
from typing import Optional

from oracle_arm_manager.logger import logger
from oracle_arm_manager.notifier import send_notification

def get_run_count(repo: str, workflow: str, since: str, status: Optional[str] = None) -> int:
    """
    透過 gh CLI 取得指定 GitHub 儲存庫和工作流程在指定時間之後的執行次數。

    此函式會呼叫 GitHub CLI (gh) 並解析其 JSON 輸出。為了安全性，
    傳入的 `repo` 與 `workflow` 會先經過正則表達式驗證，避免潛在的指令注入風險。

    Args:
        repo (str): GitHub 儲存庫名稱，格式需為 "owner/repo" (例如 "imhahac/oci-arm-instance-creator")。
        workflow (str): 工作流程的檔案名稱 (例如 "register.yml")。
        since (str): ISO 8601 格式的時間字串 (UTC)，僅計算大於此時間的紀錄 (例如 "2023-10-27T10:00:00Z")。
        status (Optional[str], optional): 篩選特定的執行狀態 (如 "failure", "success")。預設為 None (不篩選)。

    Returns:
        int: 符合條件的執行次數。若發生錯誤或驗證失敗，將回傳 0。
    """
    # 安全性驗證：確保參數只包含預期內的字元
    if not re.match(r"^[\w.-]+\/[\w.-]+$", repo):
        logger.error("無效的 repository 格式: %s", repo)
        return 0
    if not re.match(r"^[\w.-]+\.ya?ml$", workflow):
        logger.error("無效的 workflow 格式: %s", workflow)
        return 0

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
    except OSError as e:
        logger.error("執行 gh CLI 時發生系統錯誤 (可能未安裝 gh): %s", e)
        return 0
    except Exception as e:
        logger.error("取得 %s 執行次數發生未知名錯誤: %s", workflow, str(e), exc_info=True)
        return 0

def build_daily_report() -> Optional[str]:
    """
    組合每日監控報表的訊息內容。

    此函式會讀取環境變數 `GITHUB_REPOSITORY`，並呼叫 `get_run_count`
    計算過去 24 小時內自動註冊腳本失敗次數與通知腳本的執行情況。

    Returns:
        Optional[str]: 格式化後的報表字串；若缺少環境變數則回傳 None。
    """
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
    """
    產生並發送每日監控報表。

    依賴 `build_daily_report()` 取得內容，並透過 `send_notification` 推送至所有設定的通知頻道。
    """
    msg = build_daily_report()
    if msg:
        logger.info("===== 發送每日監控回報 =====\n%s", msg)
        send_notification("每日監控回報", msg, is_success=True)
