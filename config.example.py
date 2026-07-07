# Configuration Example
# Copy this to src/config.py and update with your values
# Or set environment variables

# Database Configuration (SQLite default for prototype)
# You can also set this via environment variable.
DATABASE_URL = "sqlite:///./app.db"

# Proxy Configuration
# Set PROXY_ENABLED=true to enable proxy rotation
PROXY_ENABLED = False
# Comma-separated list of proxies (format: http://user:pass@host:port or http://host:port)
PROXY_LIST = [
    "http://proxy1.example.com:8080",
    "http://proxy2.example.com:8080",
]

# Delay Configuration (seconds)
MIN_DELAY = 2
MAX_DELAY = 5
DELAY_VARIANCE = 0.3

# Retry Configuration
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2.0
INITIAL_RETRY_DELAY = 1.0

# Timeout Configuration (seconds)
PAGE_LOAD_TIMEOUT = 30
ELEMENT_WAIT_TIMEOUT = 15
IMPLICIT_WAIT = 10

# Browser Runtime Configuration
# Foreground browser by default (set True only if you explicitly want headless)
BROWSER_HEADLESS = False
PAGE_LOAD_STRATEGY = "eager"  # normal | eager | none
DELAY_SCALE = 0.5  # Lower is faster (0.5 = 50% of original waits)

# Stealth Configuration
USE_STEALTH = True
ROTATE_USER_AGENT = True
RANDOMIZE_FINGERPRINT = True

# Rate Limiting
REQUESTS_PER_HOUR = 100
REQUESTS_PER_MINUTE = 10

# Logging
LOG_LEVEL = "INFO"
LOG_DIR = "logs"

