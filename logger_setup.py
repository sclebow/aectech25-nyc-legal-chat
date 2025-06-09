import logging
import os
from pythonjsonlogger import jsonlogger
from collections import deque
import threading

# Thread-local storage for request_id
_log_context = threading.local()

def set_request_id(request_id):
    _log_context.request_id = request_id

def get_request_id():
    return getattr(_log_context, 'request_id', None)

class ContextFilter(logging.Filter):
    def filter(self, record):
        record.request_id = get_request_id()
        return True

class InMemoryLogHandler(logging.Handler):
    def __init__(self, capacity=1000):
        super().__init__()
        self.capacity = capacity
        self.records = deque(maxlen=capacity)

    def emit(self, record):
        # Store the log record and its request_id (if present)
        log_entry = self.format(record)
        request_id = getattr(record, 'request_id', None)
        self.records.append((log_entry, request_id))

    def get_logs(self, num_lines=50, request_id=None):
        # If request_id is given, filter logs for that request only
        if request_id:
            filtered = [entry for entry, rid in self.records if rid == request_id]
            return filtered[-num_lines:]
        else:
            return [entry for entry, _ in self.records][-num_lines:]

def setup_logger(name="app_logger", log_dir="logs", log_file="app.log", memory_log_capacity=1000):
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file) if not os.path.isabs(log_file) else log_file

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Prevent duplicate handlers
    if not logger.handlers:
        handler = logging.FileHandler(log_path)
        formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # Add in-memory handler
        mem_handler = InMemoryLogHandler(capacity=memory_log_capacity)
        mem_handler.setFormatter(formatter)
        logger.addHandler(mem_handler)
        logger.memory_handler = mem_handler  # Attach for easy access

        # Add context filter
        logger.addFilter(ContextFilter())

    return logger
