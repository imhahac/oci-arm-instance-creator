import logging
from config import load_config
from oci_manager import launch_instance, safe_write_file
from notifications import send_notification

# 設定日誌格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

if __name__ == "__main__":
    try:
        logging.info("🚀 啟動 OCI ARM 自動申請程序")
        cfg = load_config()
        success = launch_instance(cfg)
        
        # 寫入結果供 GitHub Actions 使用
        safe_write_file("result.txt", "success" if success else "fail")
        logging.info("🏁 程序執行完畢，結果: %s", "成功" if success else "未建立 (容量不足/預算限制/已達上限)")

    except Exception as e:
        logging.error("❌ 發生嚴重錯誤: %s", e, exc_info=True)
        safe_write_file("result.txt", "fail")
        
        # 發送失敗通知
        try:
            send_notification("🚨 OCI ARM 執行失敗", f"錯誤訊息: {str(e)}")
        except Exception as notify_err:
            logging.error("無法發送錯誤通知: %s", notify_err)
        
        raise e
