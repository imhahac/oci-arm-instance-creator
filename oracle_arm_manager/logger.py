import logging
import sys

def setup_logging() -> logging.Logger:
    import os
    logger = logging.getLogger("oracle_arm_manager")
    if logger.handlers:
        return logger

    # 從環境變數讀取日誌等級 (預設 INFO)
    log_level_str = os.getenv("OCI_LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    logger.setLevel(log_level)

    # 建立日誌格式
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 輸出至命令列
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

logger = setup_logging()
