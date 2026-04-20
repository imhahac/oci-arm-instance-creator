import json
import os
import tempfile
import argparse
import sys
from datetime import datetime
from typing import Optional, Dict, Any, List

from oracle_arm_manager.logger import logger
from oracle_arm_manager.config import load_config
from oracle_arm_manager.instance_launcher import InstanceLauncher
from oracle_arm_manager.notifier import send_notification

def write_stats(success: bool, launch_stats: Optional[Dict[str, Any]]) -> None:
    """
    將單次執行結果寫入/更新到 stats.json 供 Dashboard 讀取。
    
    Args:
        success: 本次申請是否成功 (包含已達上限的情況)。
        launch_stats: 從 InstanceLauncher 取得的詳細統計資料 (內含各區域嘗試狀況/錯誤分佈)。
    """
    stats_file = "stats.json"
    
    # 預設狀態資料結構
    stats: Dict[str, Any] = {
        "last_run": datetime.utcnow().isoformat() + "Z",
        "total_runs": 0,
        "success_runs": 0,
        "fail_runs": 0,
        "active_instances": 0,
        "regions_failed": {},
        "hourly_distribution": {}, # 記錄各小時(UTC)的成功/失敗次數
        "history": [],
    }
    
    if os.path.exists(stats_file):
        try:
            with open(stats_file, "r", encoding="utf-8") as f:
                stats.update(json.load(f))
        except Exception as e:
            logger.warning("解析 stats.json 失敗，將重新建立: %s", e)

    # 紀錄更新
    stats["last_run"] = datetime.utcnow().isoformat() + "Z"
    stats["total_runs"] += 1
    
    if success:
        stats["success_runs"] += 1
    else:
        stats["fail_runs"] += 1

    # 更新當前實例數 (如果有的話)
    if launch_stats and "active_instances" in launch_stats:
        stats["active_instances"] = launch_stats["active_instances"]

    # 小時分佈統計 (UTC)
    hour = str(datetime.utcnow().hour)
    if hour not in stats["hourly_distribution"]:
        stats["hourly_distribution"][hour] = {"success": 0, "fail": 0}
    
    if success:
        stats["hourly_distribution"][hour]["success"] += 1
    else:
        stats["hourly_distribution"][hour]["fail"] += 1

    # 累加區域失敗計數
    if not success and launch_stats:
        for r in launch_stats.get("regions_tried", []):
            stats["regions_failed"][r] = stats["regions_failed"].get(r, 0) + 1

    # 紀錄最新幾筆供線圖使用
    stats["history"].append({
        "timestamp": stats["last_run"],
        "success": success,
        "regions_tried": launch_stats.get("regions_tried", []) if launch_stats else [],
        "attempts": launch_stats.get("attempts", 0) if launch_stats else 0,
        "errors": launch_stats.get("error_distribution", {}) if launch_stats else {}
    })
    
    # 只保留近期 50 筆紀錄避免檔案過大
    if len(stats["history"]) > 50:
        stats["history"] = stats["history"][-50:]

    # 原子寫入，先寫入暫存檔，再替代原始檔案以防止中斷損毀
    try:
        fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(stats_file)), text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        os.replace(temp_path, stats_file)
    except Exception as e:
        logger.error("寫入 stats.json 失敗: %s", e)
        # 確保刪除遺留的暫存檔
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)

def _atomic_write_file(filepath: str, content: str) -> None:
    """以原子方式寫入文字檔"""
    try:
        fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(filepath)), text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(temp_path, filepath)
    except Exception as e:
        logger.error("原子寫入檔案 %s 失敗: %s", filepath, e)
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)

def check_environment(is_local: bool) -> bool:
    """
    檢查執行環境是否合法。
    若非於 GitHub Actions 環境且未加上 --local 參數，則阻擋執行。
    """
    is_github_actions = os.getenv("GITHUB_ACTIONS") == "true"
    if is_local:
        logger.info("🔧 採用本地模式 (--local) 執行，忽略環境變數檢查。")
        return True
    
    if not is_github_actions:
        logger.error("🛑 環境檢查失敗: 程式未在 GitHub Actions 環境中執行。如需在本地端執行，請帶上 --local 參數。")
        return False
        
    return True

def main() -> None:
    """
    程式的主要進入點。
    
    執行流程：
    1. 讀取並驗證環境設定 (Config)
    2. 初始化 InstanceLauncher
    3. 遍歷區域與 AD 嘗試開立實例
    4. 將執行結果寫出 (文字檔與 stats.json 統計資料)
    
    Raises:
        Exception: 任務發生不可預期或嚴重的設定錯誤時將終止並丟出。
    """
    parser = argparse.ArgumentParser(description="OCI ARM Instance Creator")
    parser.add_argument("--local", action="store_true", help="繞過 GitHub Actions 環境檢測")
    args = parser.parse_args()

    start_time = datetime.utcnow()

    try:
        logger.info("🚀 啟動重構後的 OCI ARM 自動申請程序")
        
        if not check_environment(args.local):
            sys.exit(1)
            
        cfg = load_config()
        launcher = InstanceLauncher(cfg)
        
        launch_result = launcher.run()
        success = launch_result.success
        quota_reached = launch_result.quota_reached
        
        # 三種狀態：建立成功 / 達到上限 / 失敗
        if quota_reached:
            result_str = "quota_reached"
        elif success:
            result_str = "success"
        else:
            result_str = "fail"
        
        # 使用原子寫入供 Actions 使用
        _atomic_write_file("result.txt", result_str)
        _atomic_write_file("detailed_log.txt", "\n".join(launch_result.logs))
        
        # 原子寫入供 Dashboard 讀取
        write_stats(success, launch_result.stats)
        
        if success:
            logger.info("🏁 程序執行完畢，結果: 成功 (或達上限)")
        else:
            errors = launch_result.stats.get("error_distribution", {})
            summary = ", ".join([f"{k}: {v}" for k, v in errors.items()]) or "無具體錯誤"
            logger.info("🏁 程序執行完畢，結果: 未建立 (%s)", summary)

    except Exception as e:
        logger.error("❌ 發生嚴重錯誤: %s", str(e), exc_info=True)
        _atomic_write_file("result.txt", "fail")
            
        write_stats(False, None)
        
        # 發送嚴重失敗通知
        try:
            send_notification("🚨 OCI ARM 發生異常", f"請檢察 Logs。錯誤: {str(e)[:100]}")
        except Exception as notify_err:
            logger.error("無法發送通知: %s", notify_err)
        
        raise e
    finally:
        end_time = datetime.utcnow()
        elapsed = (end_time - start_time).total_seconds()
        logger.info("⏱️ 總耗時: %.2f 秒", elapsed)

if __name__ == "__main__":
    main()
