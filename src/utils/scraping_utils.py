"""
Utility functions for web scraping operations.
Provides retry logic, selector fallback, and other common scraping utilities.
"""

import time
import random
import logging
from functools import wraps
from typing import Callable, Any, List, Optional, Tuple
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException
)
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup, Tag
from src.config import MAX_RETRIES, RETRY_BACKOFF_FACTOR, INITIAL_RETRY_DELAY
from src.exception import CustomException

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = MAX_RETRIES,
    backoff_factor: float = RETRY_BACKOFF_FACTOR,
    initial_delay: float = INITIAL_RETRY_DELAY,
    exceptions: Tuple = (Exception,)
):
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for delay between retries
        initial_delay: Initial delay in seconds
        exceptions: Tuple of exceptions to catch and retry on
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {str(e)[:100]}"
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                        # Add jitter to avoid thundering herd
                        delay += random.uniform(0, delay * 0.1)
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries + 1} attempts")
            
            raise last_exception
        return wrapper
    return decorator


def find_element_with_fallback(
    driver: WebDriver,
    selectors: List[Tuple[By, str]],
    timeout: int = 5,
    required: bool = True
) -> Optional[WebElement]:
    """
    Try multiple selectors in order until one succeeds.
    
    Args:
        driver: Selenium WebDriver instance
        selectors: List of (By, selector) tuples to try
        timeout: Timeout per selector attempt
        required: If True, raise exception if no selector works
        
    Returns:
        WebElement if found, None otherwise
    """
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    last_exception = None
    
    for by, selector in selectors:
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by, selector))
            )
            logger.debug(f"Found element using selector: {selector}")
            return element
        except (TimeoutException, NoSuchElementException) as e:
            last_exception = e
            logger.debug(f"Selector failed: {selector} - {str(e)[:50]}")
            continue
    
    if required:
        raise NoSuchElementException(
            f"Could not find element with any of {len(selectors)} selectors. "
            f"Last error: {str(last_exception)}"
        )
    
    return None


def find_elements_with_fallback(
    driver: WebDriver,
    selectors: List[Tuple[By, str]],
    timeout: int = 5,
    min_count: int = 0
) -> List[WebElement]:
    """
    Try multiple selectors until one returns at least min_count elements.
    
    Args:
        driver: Selenium WebDriver instance
        selectors: List of (By, selector) tuples to try
        timeout: Timeout per selector attempt
        min_count: Minimum number of elements required
        
    Returns:
        List of WebElements
    """
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    for by, selector in selectors:
        try:
            elements = WebDriverWait(driver, timeout).until(
                EC.presence_of_all_elements_located((by, selector))
            )
            if len(elements) >= min_count:
                logger.debug(f"Found {len(elements)} elements using selector: {selector}")
                return elements
        except (TimeoutException, NoSuchElementException):
            continue
    
    return []


def find_bs4_element_with_fallback(
    soup: BeautifulSoup,
    selectors: List[dict],
    required: bool = False
) -> Optional[Tag]:
    """
    Try multiple BeautifulSoup selectors until one succeeds.
    
    Args:
        soup: BeautifulSoup object
        selectors: List of selector dicts (e.g., [{"tag": "div", "class_": "review"}])
        required: If True, raise exception if no selector works
        
    Returns:
        Tag if found, None otherwise
    """
    for selector in selectors:
        try:
            element = soup.find(**selector)
            if element:
                logger.debug(f"Found BS4 element with selector: {selector}")
                return element
        except Exception as e:
            logger.debug(f"BS4 selector failed: {selector} - {str(e)[:50]}")
            continue
    
    if required:
        raise ValueError(f"Could not find element with any of {len(selectors)} BS4 selectors")
    
    return None


def find_bs4_elements_with_fallback(
    soup: BeautifulSoup,
    selectors: List[dict],
    min_count: int = 0
) -> List[Tag]:
    """
    Try multiple BeautifulSoup selectors until one returns at least min_count elements.
    
    Args:
        soup: BeautifulSoup object
        selectors: List of selector dicts
        min_count: Minimum number of elements required
        
    Returns:
        List of Tags
    """
    for selector in selectors:
        try:
            elements = soup.find_all(**selector)
            if len(elements) >= min_count:
                logger.debug(f"Found {len(elements)} BS4 elements with selector: {selector}")
                return elements
        except Exception:
            continue
    
    return []


def human_like_delay(min_seconds: float = 2, max_seconds: float = 5) -> None:
    """
    Human-like delay using beta distribution (favors shorter delays with occasional long pauses).
    
    Args:
        min_seconds: Minimum delay
        max_seconds: Maximum delay
    """
    # Beta distribution skewed toward shorter delays
    beta_param = random.betavariate(2, 5)
    delay = min_seconds + (max_seconds - min_seconds) * beta_param
    
    # 10% chance of longer "reading" pause
    if random.random() < 0.1:
        delay += random.uniform(2, 5)
    
    time.sleep(delay)


def check_bot_detection(page_source: str, platform: str) -> bool:
    """
    Check if page indicates bot detection/blocking.
    
    Args:
        page_source: HTML page source
        platform: Platform name (amazon, flipkart, myntra)
        
    Returns:
        True if bot detected, False otherwise
    """
    page_lower = page_source.lower()
    
    detection_patterns = {
        "amazon": [
            "to discuss automated access",
            "sorry, we just need to make sure you're not a robot",
            "enter the characters you see",
            "captcha",
            "access denied",
        ],
        "flipkart": [
            "access denied",
            "blocked",
            "captcha",
            "verify you are human",
        ],
        "myntra": [
            "access denied",
            "blocked",
            "captcha",
        ],
    }
    
    patterns = detection_patterns.get(platform.lower(), [])
    for pattern in patterns:
        if pattern in page_lower:
            logger.warning(f"Bot detection pattern found on {platform}: {pattern}")
            return True
    
    return False


def extract_text_safe(element: Optional[Tag], default: str = "N/A") -> str:
    """
    Safely extract text from BeautifulSoup element.
    
    Args:
        element: BeautifulSoup Tag or None
        default: Default value if element is None or empty
        
    Returns:
        Extracted text or default
    """
    if element is None:
        return default
    
    try:
        text = element.get_text(strip=True)
        return text if text else default
    except Exception:
        return default


def normalize_rating(rating_text: str) -> str:
    """
    Normalize rating text to numeric string.
    
    Args:
        rating_text: Raw rating text (e.g., "4.5 out of 5", "4.5★", "4.5")
        
    Returns:
        Normalized rating string (e.g., "4.5")
    """
    import re
    
    if not rating_text:
        return "N/A"
    
    # Remove stars and common text
    cleaned = rating_text.replace("★", "").replace("☆", "").strip()
    cleaned = re.sub(r"out of \d+", "", cleaned, flags=re.IGNORECASE).strip()
    
    # Extract numeric value
    match = re.search(r'(\d+\.?\d*)', cleaned)
    if match:
        rating = float(match.group(1))
        # Clamp to valid range
        if 0 <= rating <= 5:
            return str(rating)
    
    return "N/A"

