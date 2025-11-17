from abc import ABC, abstractmethod
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup as bs
import pandas as pd
import time
import os, sys
from src.exception import CustomException


class BaseScraper(ABC):
    """Abstract base class for all e-commerce platform scrapers."""
    
    def __init__(self, product_name: str, no_of_products: int):
        """
        Initialize the scraper with common setup.
        
        Args:
            product_name: Name of the product to search for
            no_of_products: Number of products to scrape reviews from
        """
        options = Options()
        # Suppress Chrome verbose logging and remove automation flags
        options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        # Set realistic user-agent to avoid bot detection
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        # HTTP/2 protocol error fixes
        options.add_argument("--disable-http2")
        options.add_argument("--disable-quic")
        # Suppress GCM/Chrome sync errors (cosmetic only)
        options.add_argument("--disable-gcm")
        options.add_argument("--disable-background-networking")
        # Additional stealth options
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        # Common options can be uncommented as needed
        # options.add_argument("--no-sandbox")
        # options.add_argument("--disable-dev-shm-usage")
        # options.add_argument('--headless')
        
        self.driver = webdriver.Chrome(options=options)
        # Execute script to remove webdriver property (bot detection)
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })
        self.driver.implicitly_wait(10)
        self.wait = WebDriverWait(self.driver, 15)
        self.product_name = product_name
        self.no_of_products = no_of_products
        
        # Will be set by extract_reviews
        self.product_title = None
        self.product_rating_value = None
        self.product_price = None
    
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
            time.sleep(3)
            
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
                    skipped_products += 1
                    if review_len < len(product_urls):
                        product_urls.pop(review_len)
            
            self.driver.quit()
            
            if not product_details:
                raise CustomException(
                    f"Scraping failed: Found {len(product_urls)} products but extracted 0 reviews. "
                    f"Skipped {skipped_products} products (no reviews or extraction failed). "
                    f"This may indicate the website structure changed or products have no reviews.",
                    sys
                )
            
            data = pd.concat(product_details, axis=0)
            
            # Add Platform column
            data["Platform"] = self.platform_name
            
            # Ensure all required columns exist
            required_columns = [
                "Product Name", "Over_All_Rating", "Price", 
                "Date", "Rating", "Name", "Comment", "Platform"
            ]
            for col in required_columns:
                if col not in data.columns:
                    data[col] = None
            
            # Reorder columns
            data = data[required_columns]
            
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

