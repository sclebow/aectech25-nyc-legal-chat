import logging
import os
from pythonjsonlogger import jsonlogger

def setup_logger(name="app_logger", log_dir="logs", log_file="app.log"):
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file) if not os.path.isabs(log_file) else log_file

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Prevent duplicate handlers
    if not logger.handlers:
        handler = logging.FileHandler(log_path)
        formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
