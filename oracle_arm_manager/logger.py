import logging
import sys
import os
import json
from typing import Any

class JsonFormatter(logging.Formatter):
    """自定義 JSON 日誌格式器，適合送往雲端 Log 分析平台"""
    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, ensure_ascii=False)

def setup_logging() -> logging.Logger:
    """
    初始化並設定主要 Logger。
    
    支援透過 `OCI_LOG_LEVEL` 設定等級 (INFO/DEBUG/WARNING 等)。
    支援透過 `OCI_LOG_FORMAT` 切換格式 (TEXT/JSON)。
    
    Returns:
        設定完成的 logging.Logger 實例。
    """
    logger = logging.getLogger("oracle_arm_manager")
    if logger.handlers:
        return logger

    log_level_str = os.getenv("OCI_LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    logger.setLevel(log_level)

    log_format_str = os.getenv("OCI_LOG_FORMAT", "TEXT").upper()
    console_handler = logging.StreamHandler(sys.stdout)

    if log_format_str == "JSON":
        formatter: logging.Formatter = JsonFormatter(datefmt="%Y-%m-%dT%H:%M:%SZ")
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

logger = setup_logging()
