from abc import ABC, abstractmethod
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    InvalidSessionIdException,
    WebDriverException
)
from selenium_stealth import stealth
from bs4 import BeautifulSoup as bs
import pandas as pd
import time
import random
import os, sys
import logging
from typing import Optional, List
from src.exception import CustomException
from src.utils.rate_limiter import RateLimiter
from src.utils.sentiment_analyzer import analyze_review_comment
from src.config import (
    REQUESTS_PER_MINUTE,
    BROWSER_HEADLESS,
    PAGE_LOAD_STRATEGY,
    PAGE_LOAD_TIMEOUT,
    ELEMENT_WAIT_TIMEOUT,
    IMPLICIT_WAIT,
    DELAY_SCALE,
)

# Configure logging
# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

# Configure logging only if not already configured
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f'logs/scraper_{time.strftime("%Y-%m-%d")}.log'),
            logging.StreamHandler()
        ]
    )
logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all e-commerce platform scrapers."""
    
    # Realistic user agents pool (updated 2024)
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    
    # WebGL vendor/renderer combinations for fingerprint randomization
    WEBGL_VENDORS = [
        ("Intel Inc.", "Intel Iris OpenGL Engine"),
        ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 6GB Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon RX 580 Series Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ]
    
    def __init__(self, product_name: str, no_of_products: int, proxy: Optional[str] = None):
        """
        Initialize the scraper with common setup using selenium-stealth.

        Args:
            product_name: Name of the product to search for
            no_of_products: Number of products to scrape reviews from
            proxy: Optional proxy string in format "http://user:pass@host:port" or "http://host:port"
        """
        # Configure Chrome options for stealth
        options = Options()
        options.page_load_strategy = PAGE_LOAD_STRATEGY

        # Docker-specific flags are only needed in containers.
        running_in_docker = os.path.exists("/.dockerenv") or os.getenv("RUNNING_IN_DOCKER", "False").lower() == "true"

        # Suppress Chrome verbose logging and automation flags
        options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)

        # Disable save password prompts
        options.add_experimental_option('prefs', {
            'credentials_enable_service': False,
            'profile.password_manager_enabled': False
        })

        # Disable blink features that reveal automation
        options.add_argument("--disable-blink-features=AutomationControlled")

        # Additional stealth arguments
        options.add_argument("--disable-web-security")
        options.add_argument("--disable-site-isolation-trials")
        options.add_argument("--disable-features=IsolateOrigins,site-per-process")

        # Set window size to common resolution (randomize slightly)
        width = random.choice([1920, 1366, 1536, 1440])
        height = random.choice([1080, 768, 864, 900])
        options.add_argument(f"--window-size={width},{height}")
        options.add_argument("--start-maximized")

        # Foreground headed browser is the default for consistency.
        if BROWSER_HEADLESS:
            options.add_argument("--headless=new")
            logger.info("Browser mode: headless")
        else:
            logger.info("Browser mode: foreground (headed)")

        # Suppress GCM/Chrome sync errors (cosmetic only)
        options.add_argument("--disable-gcm")
        options.add_argument("--disable-background-networking")

        # Docker/container-only flags.
        if running_in_docker:
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-setuid-sandbox")
            options.add_argument("--disable-gpu")
        elif BROWSER_HEADLESS:
            # Keep GPU off in local headless mode for stability.
            options.add_argument("--disable-gpu")
        
        # Disable automation indicators
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")
        
        # Proxy configuration
        if proxy:
            options.add_argument(f'--proxy-server={proxy}')
            logger.info(f"Using proxy: {proxy.split('@')[-1] if '@' in proxy else proxy}")

        # Initialize Chrome driver.
        # Default path: Selenium Manager (keeps driver version aligned with Chrome).
        # Override path: CHROMEDRIVER_PATH env var.
        driver_path = os.getenv("CHROMEDRIVER_PATH", "").strip()
        local_driver_candidates = [
            os.path.join(os.getcwd(), "venv", "Lib", "site-packages", "chromedriver_binary", "chromedriver.exe"),
            os.path.join(os.getcwd(), ".venv", "Lib", "site-packages", "chromedriver_binary", "chromedriver.exe"),
        ]

        if driver_path and not os.path.exists(driver_path):
            logger.warning(f"CHROMEDRIVER_PATH does not exist: {driver_path}. Ignoring it.")
            driver_path = ""

        try:
            if driver_path:
                logger.info(f"Using explicit ChromeDriver path: {driver_path}")
                service = Service(executable_path=driver_path)
                self.driver = webdriver.Chrome(service=service, options=options)
            else:
                self.driver = webdriver.Chrome(options=options)
        except Exception as e:
            if driver_path:
                logger.error(f"Failed to initialize Chrome driver with CHROMEDRIVER_PATH: {e}")
                raise CustomException(f"Chrome driver initialization failed: {e}", sys)

            # Selenium Manager failed. Try known local bundled chromedriver binaries as fallback.
            fallback_error = e
            self.driver = None
            for candidate in local_driver_candidates:
                if not os.path.exists(candidate):
                    continue
                try:
                    logger.warning(
                        "Selenium Manager failed; trying local ChromeDriver fallback at %s",
                        candidate,
                    )
                    service = Service(executable_path=candidate)
                    self.driver = webdriver.Chrome(service=service, options=options)
                    logger.info(f"Using local ChromeDriver fallback: {candidate}")
                    break
                except Exception as fallback_exc:
                    fallback_error = fallback_exc
                    continue

            if not self.driver:
                logger.error(f"Failed to initialize Chrome driver: {fallback_error}")
                raise CustomException(f"Chrome driver initialization failed: {fallback_error}", sys)

        # Randomize user agent and WebGL fingerprint
        user_agent = random.choice(self.USER_AGENTS)
        webgl_vendor, webgl_renderer = random.choice(self.WEBGL_VENDORS)
        
        # Randomize platform based on user agent
        if "Macintosh" in user_agent:
            platform = "MacIntel"
        elif "Linux" in user_agent:
            platform = "Linux x86_64"
        else:
            platform = "Win32"

        # Apply selenium-stealth to make the driver undetectable
        try:
            stealth(self.driver,
                    languages=["en-US", "en"],
                    vendor=webgl_vendor,
                    platform=platform,
                    webgl_vendor=webgl_vendor,
                    renderer=webgl_renderer,
                    fix_hairline=True,
            )
        except Exception as e:
            logger.warning(f"Stealth configuration warning: {e}")

        # Set randomized user agent via CDP
        try:
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": user_agent})
            logger.debug(f"Set user agent: {user_agent[:50]}...")
        except Exception as e:
            logger.warning(f"Failed to set user agent via CDP: {e}")

        # Set additional CDP commands to mask automation
        try:
            # Override navigator.webdriver
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                '''
            })
            
            # Override Chrome runtime
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    window.chrome = {
                        runtime: {}
                    };
                '''
            })
            
            # Override permissions
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                '''
            })
        except Exception as e:
            logger.warning(f"CDP command execution warning: {e}")

        self.driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        self.driver.implicitly_wait(IMPLICIT_WAIT)
        self.wait = WebDriverWait(self.driver, ELEMENT_WAIT_TIMEOUT)
        self.product_name = product_name
        self.no_of_products = no_of_products
        self.proxy = proxy
        self.delay_scale = DELAY_SCALE

        # Initialize rate limiter
        self.rate_limiter = RateLimiter(max_calls=REQUESTS_PER_MINUTE, period=60.0)
        logger.info(f"Rate limiter initialized: {REQUESTS_PER_MINUTE} requests per minute")

        # Will be set by extract_reviews
        self.product_title = None
        self.product_rating_value = None
        self.product_price = None
        
        logger.info(f"Initialized {self.platform_name} scraper for '{product_name}'")

    def scaled_sleep(self, seconds: float, min_sleep: float = 0.1) -> None:
        """
        Sleep using global delay scaling to speed up scraper runs consistently.
        """
        sleep_seconds = max(min_sleep, float(seconds) * self.delay_scale)
        time.sleep(sleep_seconds)
    
    def _apply_rate_limit(self) -> None:
        """
        Apply rate limiting before making a request.
        Should be called before every driver.get() call.
        """
        self.rate_limiter.acquire()
    
    def is_session_valid(self) -> bool:
        """
        Check if the current WebDriver session is still valid.
        
        Returns:
            True if session is valid, False otherwise
        """
        try:
            if not self.driver:
                return False
            # Try a simple operation to check if session is alive
            self.driver.current_url
            return True
        except (InvalidSessionIdException, WebDriverException, AttributeError):
            return False
        except Exception:
            # Other exceptions might indicate session issues
            return False
    
    def random_delay(self, min_seconds=2, max_seconds=5, human_like=True):
        """
        Add a random delay to mimic human behavior with human-like timing patterns.

        Args:
            min_seconds: Minimum delay in seconds
            max_seconds: Maximum delay in seconds
            human_like: If True, use human-like timing curve (favor shorter delays with occasional long pauses)
        """
        if human_like:
            # Human-like delay: most delays are short-medium, occasional longer pauses
            # Use beta distribution to favor shorter delays
            beta_param = random.betavariate(2, 5)  # Skewed toward shorter delays
            delay = min_seconds + (max_seconds - min_seconds) * beta_param
            
            # Occasionally add a longer "reading" pause (10% chance)
            if random.random() < 0.1:
                delay += random.uniform(2, 5)
        else:
            delay = random.uniform(min_seconds, max_seconds)

        self.scaled_sleep(delay, min_sleep=0.05)

    def human_like_mouse_move(self):
        """
        Simulate human-like mouse movements using JavaScript with bezier curves.
        """
        try:
            # Simulate reading behavior: scroll in small increments with pauses
            scroll_steps = random.randint(3, 6)
            for i in range(scroll_steps):
                # Bezier-like scroll (smooth acceleration/deceleration)
                progress = i / scroll_steps
                # Ease-in-out curve
                ease = progress * progress * (3 - 2 * progress)
                
                scroll_amount = random.randint(200, 400)
                current_pos = self.driver.execute_script("return window.pageYOffset;")
                target_pos = current_pos + int(scroll_amount * ease)
                
                self.driver.execute_script(f"window.scrollTo(0, {target_pos});")
                
                # Variable pause (longer pauses simulate reading)
                pause_time = random.uniform(0.3, 1.2) if i < scroll_steps - 1 else random.uniform(0.5, 1.5)
                self.scaled_sleep(pause_time, min_sleep=0.05)
            
            # Occasionally scroll back up slightly (human behavior)
            if random.random() < 0.3:
                scroll_back = random.randint(50, 150)
                current_pos = self.driver.execute_script("return window.pageYOffset;")
                self.driver.execute_script(f"window.scrollTo(0, {max(0, current_pos - scroll_back)});")
                self.scaled_sleep(random.uniform(0.2, 0.5), min_sleep=0.05)
        except Exception as e:
            logger.debug(f"Mouse movement simulation error: {e}")
            pass

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform name (e.g., 'myntra', 'flipkart', 'amazon')."""
        pass
    
    @abstractmethod
    def scrape_product_urls(self, product_name: str) -> list:
        """
        Scrape product URLs from search results.
        
        Args:
            product_name: Product name to search for
            
        Returns:
            List of product URL paths/identifiers
        """
        pass
    
    @abstractmethod
    def extract_reviews(self, product_link) -> object:
        """
        Extract review link/object from product page.
        
        Args:
            product_link: Product URL or identifier
            
        Returns:
            Review link object or None if no reviews found
        """
        pass
    
    @abstractmethod
    def extract_products(self, product_reviews) -> pd.DataFrame:
        """
        Extract individual reviews from review page.
        
        Args:
            product_reviews: Review link object or URL
            
        Returns:
            DataFrame with columns: Product Name, Over_All_Rating, Price, 
            Date, Rating, Name, Comment, Platform
        """
        pass
    
    def scroll_to_load_reviews(self):
        """
        Scroll to load more reviews on dynamic pages.
        Common implementation that can be overridden if needed.
        """
        self.driver.set_window_size(1920, 1080)
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        while True:
            self.driver.execute_script("window.scrollBy(0, 1000);")
            self.scaled_sleep(3)
            
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            
            last_height = new_height
    
    def get_review_data(self) -> pd.DataFrame:
        """
        Main orchestrator method to get review data.
        Common implementation that follows the pattern:
        1. Scrape product URLs
        2. For each product, extract reviews
        3. Combine all reviews into a single DataFrame
        4. Add Platform column
        5. Save to CSV
        
        Returns:
            DataFrame with all reviews including Platform column
            
        Raises:
            CustomException: With descriptive error message if scraping fails
        """
        try:
            product_urls = self.scrape_product_urls(product_name=self.product_name)
            
            if not product_urls:
                raise CustomException(
                    f"No products found for '{self.product_name}' on {self.platform_name}. "
                    "Try a different search term or check if the website structure has changed.",
                    sys
                )
            
            product_details = []
            review_len = 0
            skipped_products = 0
            max_attempts = len(product_urls) * 2  # Prevent infinite loops
            
            attempts = 0
            while review_len < self.no_of_products and review_len < len(product_urls) and attempts < max_attempts:
                attempts += 1
                
                if review_len >= len(product_urls):
                    break
                    
                # Check if session is still valid before processing next product
                if not self.is_session_valid():
                    logger.error("Browser session lost during scraping. Cannot continue.")
                    break
                
                product_url = product_urls[review_len]
                review = self.extract_reviews(product_url)
                
                if review:
                    product_detail = self.extract_products(review)
                    if product_detail is not None and not product_detail.empty:
                        product_details.append(product_detail)
                        review_len += 1
                    else:
                        skipped_products += 1
                        if review_len < len(product_urls):
                            product_urls.pop(review_len)
                else:
                    # Product page failed to load - skip it
                    skipped_products += 1
                    if review_len < len(product_urls):
                        product_urls.pop(review_len)
            
            self.driver.quit()
            
            if not product_details:
                raise CustomException(
                    f"Scraping failed: Found {len(product_urls)} products but extracted 0 product entries. "
                    f"Skipped {skipped_products} products (product pages failed to load or extraction failed). "
                    f"This may indicate the website structure changed or network issues.",
                    sys
                )
            
            data = pd.concat(product_details, axis=0)
            
            # Add Platform column
            data["Platform"] = self.platform_name
            
            # Apply sentiment analysis to reviews
            logger.info("Analyzing sentiment for reviews...")
            sentiment_data = []
            for idx, row in data.iterrows():
                comment = str(row.get("Comment", ""))
                sentiment_info = analyze_review_comment(comment)
                sentiment_data.append(sentiment_info)
            
            # Add sentiment columns to DataFrame
            if sentiment_data:
                data["Sentiment_Score"] = [s["sentiment_score"] for s in sentiment_data]
                data["Sentiment_Label"] = [s["sentiment_label"] for s in sentiment_data]
                data["Subjectivity"] = [s["subjectivity"] for s in sentiment_data]
            else:
                data["Sentiment_Score"] = None
                data["Sentiment_Label"] = None
                data["Subjectivity"] = None
            
            logger.info(f"Sentiment analysis completed for {len(data)} reviews")
            
            # Ensure all required columns exist
            required_columns = [
                "Product Name", "Over_All_Rating", "Price", 
                "Date", "Rating", "Name", "Comment", "Platform"
            ]
            for col in required_columns:
                if col not in data.columns:
                    data[col] = None
            
            # Reorder columns (include sentiment columns)
            all_columns = required_columns + ["Sentiment_Score", "Sentiment_Label", "Subjectivity"]
            # Only include columns that exist
            existing_columns = [col for col in all_columns if col in data.columns]
            data = data[existing_columns]
            
            data.to_csv("data.csv", index=False)
            
            return data
            
        except CustomException:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            raise
        except Exception as e:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            raise CustomException(e, sys)

