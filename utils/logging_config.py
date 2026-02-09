"""
Structured JSON Logging Configuration for e-KYC API.

Provides JSON-formatted logs with:
- timestamp (ISO 8601)
- level
- message
- logger name
- Extra context (transaction_id, endpoint, latency_ms, etc.)
"""
import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs JSON-structured logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add any extra fields passed via logging.info(..., extra={...})
        for key in ["transaction_id", "endpoint", "latency_ms", "status_code", "method", "path"]:
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)
        
        return json.dumps(log_entry)


def configure_logging(level: str = "INFO", json_format: bool = True) -> None:
    """
    Configure application logging.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        json_format: If True, use JSON formatting; else use plain text
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))
    
    root_logger.addHandler(handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def log_execution_time(func):
    """
    Decorator to log function execution time.
    
    Logs at INFO level with function name and duration in milliseconds.
    Works with both synchronous and asynchronous functions.
    
    Usage:
        @log_execution_time
        def my_function():
            ...
            
        @log_execution_time
        async def my_async_function():
            ...
    """
    import functools
    import time
    import asyncio
    
    logger = logging.getLogger(func.__module__)
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"{func.__name__} completed in {elapsed_ms:.2f}ms",
                extra={"latency_ms": round(elapsed_ms, 2)}
            )
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"{func.__name__} completed in {elapsed_ms:.2f}ms",
                extra={"latency_ms": round(elapsed_ms, 2)}
            )
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper
