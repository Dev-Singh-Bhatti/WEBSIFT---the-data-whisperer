# src/config.py
import os
from typing import List, Optional

# MongoDB Configuration
MONGO_DB_URL = os.getenv("MONGO_DB_URL", "your_mongodb_url_here")
# SQLite Configuration (default storage for prototype)
# Example: sqlite:///./app.db
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

# Scraping Configuration
# Proxy settings (set via environment variables or modify here)
PROXY_ENABLED = os.getenv("PROXY_ENABLED", "False").lower() == "true"
PROXY_LIST: List[str] = os.getenv("PROXY_LIST", "").split(",") if os.getenv("PROXY_LIST") else []
# Format: "http://user:pass@host:port" or "http://host:port"

# Delay Configuration (in seconds)
MIN_DELAY = float(os.getenv("MIN_DELAY", "2"))
MAX_DELAY = float(os.getenv("MAX_DELAY", "5"))
DELAY_VARIANCE = float(os.getenv("DELAY_VARIANCE", "0.3"))  # Human-like variance factor

# Retry Configuration
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "2.0"))
INITIAL_RETRY_DELAY = float(os.getenv("INITIAL_RETRY_DELAY", "1.0"))

# Timeout Configuration (in seconds)
PAGE_LOAD_TIMEOUT = int(os.getenv("PAGE_LOAD_TIMEOUT", "30"))
ELEMENT_WAIT_TIMEOUT = int(os.getenv("ELEMENT_WAIT_TIMEOUT", "15"))
IMPLICIT_WAIT = int(os.getenv("IMPLICIT_WAIT", "10"))

# Browser Runtime Configuration
# Foreground (headed) mode is default for higher consistency while debugging.
BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "False").lower() == "true"
# Faster page loads: "eager" waits for DOMContentLoaded instead of all assets.
PAGE_LOAD_STRATEGY = os.getenv("PAGE_LOAD_STRATEGY", "eager").lower()
if PAGE_LOAD_STRATEGY not in {"normal", "eager", "none"}:
    PAGE_LOAD_STRATEGY = "eager"
# Scale all fixed sleeps in scraper code. 0.5 means 50% of original wait.
DELAY_SCALE = float(os.getenv("DELAY_SCALE", "0.5"))
if DELAY_SCALE <= 0:
    DELAY_SCALE = 0.5

# Stealth Configuration
USE_STEALTH = os.getenv("USE_STEALTH", "True").lower() == "true"
ROTATE_USER_AGENT = os.getenv("ROTATE_USER_AGENT", "True").lower() == "true"
RANDOMIZE_FINGERPRINT = os.getenv("RANDOMIZE_FINGERPRINT", "True").lower() == "true"

# Rate Limiting
REQUESTS_PER_HOUR = int(os.getenv("REQUESTS_PER_HOUR", "100"))
REQUESTS_PER_MINUTE = int(os.getenv("REQUESTS_PER_MINUTE", "10"))

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = os.getenv("LOG_DIR", "logs")

# Create logs directory if it doesn't exist
os.makedirs(LOG_DIR, exist_ok=True)
