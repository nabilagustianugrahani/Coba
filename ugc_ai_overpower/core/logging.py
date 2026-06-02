import os, sys, json, logging, logging.handlers
from datetime import datetime, timezone

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0]:
            log["exception"] = self.formatException(record.exc_info)
        return json.dumps(log, ensure_ascii=False)

def setup_logging(name="skynet", level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    os.makedirs("logs", exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        f"logs/{name}.log", maxBytes=10_485_760, backupCount=5
    )
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(console)
    return logger
