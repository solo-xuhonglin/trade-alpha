"""Structured logging with automatic context injection."""

import logging
import os
import sys
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_module_var: ContextVar[str] = ContextVar("module", default="-")
_method_var: ContextVar[str] = ContextVar("method", default="-")


class StructuredFormatter(logging.Formatter):
    """Custom formatter: timestamp [LEVEL] [request_id] [module] [method] message"""

    def format(self, record: logging.LogRecord) -> str:
        record.request_id = _request_id_var.get()
        record.module = _module_var.get()
        record.method = _method_var.get()
        return super().format(record)


def setup_logging(log_level: Optional[str] = None, log_dir: Optional[str] = None) -> None:
    """Setup logging with console and file handlers."""
    level = log_level or os.getenv("LOG_LEVEL", "DEBUG")

    if log_dir:
        log_path = Path(log_dir)
    else:
        log_path = Path(__file__).parent.parent.parent.parent / "logs"
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / "trade_alpha.log"

    formatter = StructuredFormatter(
        fmt="%(asctime)s.%(msecs)03d [%(levelname)s] [%(request_id)s] [%(filename)s:%(lineno)d] [%(method)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    if not root_logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").propagate = False
    logging.getLogger("uvicorn.error").propagate = False


class ContextLogger:
    """Logger wrapper that automatically injects module and method context."""

    def __init__(self, module: str):
        self._module = module
        self._logger = logging.getLogger(module)

    def _log(self, method: str, msg: str, level: int = logging.INFO, *args, **kwargs):
        _module_var.set(self._module)
        _method_var.set(method)
        self._logger.log(level, msg, *args, stacklevel=4, **kwargs)

    def _log_with_fallback(self, method: str, msg: str, level: int, *args, **kwargs):
        if not msg:
            msg, method = method, "-"
        self._log(method, msg, level, *args, **kwargs)

    def debug(self, method: str, msg: str = "", *args, **kwargs):
        self._log_with_fallback(method, msg, logging.DEBUG, *args, **kwargs)

    def info(self, method: str, msg: str = "", *args, **kwargs):
        self._log_with_fallback(method, msg, logging.INFO, *args, **kwargs)

    def warning(self, method: str, msg: str = "", *args, **kwargs):
        self._log_with_fallback(method, msg, logging.WARNING, *args, **kwargs)

    def error(self, method: str, msg: str = "", *args, **kwargs):
        kwargs.setdefault("exc_info", True)
        self._log_with_fallback(method, msg, logging.ERROR, *args, **kwargs)

    def exception(self, method: str, msg: str = "", *args, **kwargs):
        kwargs.setdefault("exc_info", True)
        self._log_with_fallback(method, msg, logging.ERROR, *args, **kwargs)


def get_logger(module: str) -> ContextLogger:
    """Get a logger instance for the specified module."""
    return ContextLogger(module)


def get_request_id() -> str:
    """Get current request ID."""
    return _request_id_var.get()


def generate_request_id() -> str:
    """Generate a new request ID."""
    req_id = f"req_{uuid.uuid4().hex[:8]}"
    _request_id_var.set(req_id)
    return req_id
