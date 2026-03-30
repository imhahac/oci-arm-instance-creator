import logging
import sys

def setup_logging() -> logging.Logger:
    logger = logging.getLogger("oracle_arm_manager")
    # 避免重複添加 handlers
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

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
