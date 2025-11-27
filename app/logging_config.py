"""
Logging configuration for production environment.
Uses structured JSON logging for better observability.
"""

import logging
import sys
import os
from pythonjsonlogger import jsonlogger

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Create logger
logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

# JSON formatter for structured logging
json_formatter = jsonlogger.JsonFormatter(
    '%(timestamp)s %(level)s %(name)s %(message)s',
    timestamp=True
)

# Console handler with JSON formatting (for production)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(json_formatter)
logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
