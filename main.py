import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

from oracle_arm_manager.logger import logger
from oracle_arm_manager.config import load_config
from oracle_arm_manager.instance_launcher import InstanceLauncher
from oracle_arm_manager.notifier import send_notification

def write_stats(success: bool, launch_stats: Optional[Dict[str, Any]]) -> None:
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

    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)


def main() -> None:
    try:
        logger.info("🚀 啟動重構後的 OCI ARM 自動申請程序")
        cfg = load_config()
        launcher = InstanceLauncher(cfg)
        
        launch_result = launcher.run()
        success = launch_result.success
        
        # 寫入供 Actions 使用
        with open("result.txt", "w", encoding="utf-8") as f:
            f.write("success" if success else "fail")
            
        with open("detailed_log.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(launch_result.logs))
        
        # 寫入供 Dashboard 讀取
        write_stats(success, launch_result.stats)
        
        logger.info("🏁 程序執行完畢，結果: %s", "成功 (或達上限)" if success else "未建立 (容量不足或速率限制)")

    except Exception as e:
        logger.error("❌ 發生嚴重錯誤: %s", str(e), exc_info=True)
        with open("result.txt", "w", encoding="utf-8") as f:
            f.write("fail")
            
        write_stats(False, None)
        
        # 發送嚴重失敗通知
        try:
            send_notification("🚨 OCI ARM 發生異常", f"請檢察 Logs。錯誤: {str(e)[:100]}")
        except Exception as notify_err:
            logger.error("無法發送通知: %s", notify_err)
        
        raise e

if __name__ == "__main__":
    main()
