# ============================================================
# 统一日志模块 — JSON 格式，无敏感信息输出
# ============================================================

import logging
import sys

from pythonjsonlogger import jsonlogger

from app.core.config import settings


class SensitiveDataFilter(logging.Filter):
    """过滤日志中的敏感信息（Token、密码等）"""

    SENSITIVE_PATTERNS = ["password", "token", "secret", "authorization", "api_key"]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage().lower()
        for pattern in self.SENSITIVE_PATTERNS:
            if pattern in message:
                record.msg = "[REDACTED] log contains sensitive keyword"
                record.args = ()
                break
        return True


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("bidai")
    logger.setLevel(settings.log_level.upper())

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = jsonlogger.JsonFormatter(  # type: ignore[no-untyped-call]
            "%(asctime)s %(levelname)s %(name)s %(message)s %(pathname)s %(lineno)d",
            rename_fields={"asctime": "timestamp", "levelname": "level"},
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter())
        logger.addHandler(handler)

    return logger


logger = setup_logging()
