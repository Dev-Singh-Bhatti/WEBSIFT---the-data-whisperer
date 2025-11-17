from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from src.exception import CustomException
from bs4 import BeautifulSoup as bs
import pandas as pd
import os, sys
import time
import re
from urllib.parse import quote
from src.scrapper.base_scraper import BaseScraper


class AmazonScraper(BaseScraper):
    platform_name = "amazon"
    
    def scrape_product_urls(self, product_name: str) -> list:
        """
        Scrape product URLs from Amazon search results.
        
        Args:
            product_name: Product name to search for
            
        Returns:
            List of product URLs
        """
        try:
            encoded_query = quote(product_name)
            search_url = f"https://www.amazon.in/s?k={encoded_query}"
            
            # Add headers to mimic browser request
            self.driver.get(search_url)
            time.sleep(3)
            
            # Scroll to load more products
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            page_source = self.driver.page_source
            html = bs(page_source, "html.parser")
            
            product_urls = []
            
            # Amazon product links have class: a-link-normal s-underline-text s-underline-text-text-display-block
            # Also can be in: a-link-normal s-link-style a-text-normal
            product_links = html.find_all("a", href=True, class_=lambda x: x and ("s-underline-text" in str(x) or "s-link-style" in str(x)))
            
            for link in product_links:
                href = link.get("href", "")
                if href:
                    # Filter for product URLs (contain /dp/ or /gp/product/)
                    if "/dp/" in href or "/gp/product/" in href:
                        # Convert relative URLs to absolute
                        if href.startswith("/"):
                            href = f"https://www.amazon.in{href}"
                        elif not href.startswith("http"):
                            href = f"https://www.amazon.in/{href}"
                        
                        # Extract clean URL (remove ref parameters)
                        if "/dp/" in href:
                            clean_url = href.split("/dp/")[0] + "/dp/" + href.split("/dp/")[1].split("/")[0]
                        elif "/gp/product/" in href:
                            clean_url = href.split("/gp/product/")[0] + "/gp/product/" + href.split("/gp/product/")[1].split("/")[0]
                        else:
                            clean_url = href.split("?")[0]
                        
                        if clean_url not in product_urls:
                            product_urls.append(clean_url)
            
            return product_urls[:self.no_of_products * 2]  # Get extra URLs in case some don't have reviews
            
        except Exception as e:
            raise CustomException(e, sys)
    
    def extract_reviews(self, product_url):
        """
        Navigate to product page, extract metadata, and scroll to reviews section.
        Returns product URL to stay on same page for review extraction.
        
        Args:
            product_url: Full Amazon product URL
            
        Returns:
            Product URL if successful, None if product not found
        """
        try:
            self.driver.get(product_url)
            time.sleep(3)
            
            page_source = self.driver.page_source
            
            # Check for bot detection/blocked page
            if "To discuss automated access to Amazon data please contact" in page_source:
                raise CustomException(
                    f"Page {product_url} was blocked by Amazon. Please try using better proxies or reduce request frequency.",
                    sys
                )
            
            html = bs(page_source, "html.parser")
            
            # Extract product title - try multiple selectors
            title_elem = html.find("span", {"id": "productTitle"})
            if not title_elem:
                title_elem = html.find("h1", {"class": "a-size-large"})
            if not title_elem:
                title_elem = html.find("h1", class_=lambda x: x and "product-title" in str(x).lower())
            if title_elem:
                self.product_title = title_elem.text.strip()
            else:
                self.product_title = "Unknown Product"
            
            # Extract overall rating - improved parsing like reference
            rating_elem = html.find("span", {"class": "a-icon-alt"})
            if rating_elem:
                rating_text = rating_elem.text.strip()
                # Reference pattern: split ' out of' and take first part
                if ' out of' in rating_text:
                    self.product_rating_value = rating_text.split(' out of')[0].strip()
                else:
                    # Fallback: extract number
                    rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                    self.product_rating_value = rating_match.group(1) if rating_match else "N/A"
            else:
                # Try alternative selectors
                rating_elem = html.find("span", {"id": "acrPopover"})
                if rating_elem:
                    rating_text = rating_elem.get("title", "")
                    if ' out of' in rating_text:
                        self.product_rating_value = rating_text.split(' out of')[0].strip()
                    else:
                        self.product_rating_value = "N/A"
                else:
                    self.product_rating_value = "N/A"
            
            # Extract price - improved extraction
            price_elem = html.find("span", {"class": "a-price-whole"})
            if price_elem:
                price_text = price_elem.text.strip().replace(",", "")
                self.product_price = f"₹{price_text}"
            else:
                price_elem = html.find("span", {"id": "priceblock_dealprice"})
                if not price_elem:
                    price_elem = html.find("span", {"id": "priceblock_ourprice"})
                if not price_elem:
                    price_elem = html.find("span", {"id": "priceblock_saleprice"})
                if price_elem:
                    price_text = price_elem.text.strip().replace(",", "")
                    self.product_price = price_text
                else:
                    self.product_price = "N/A"
            
            # Scroll to reviews section at bottom of page
            self._scroll_to_reviews_section()
            
            return product_url
                
        except CustomException:
            raise
        except Exception as e:
            raise CustomException(e, sys)
    
    def _scroll_to_reviews_section(self):
        """
        Scroll to reviews section on product page and wait for reviews to load.
        """
        try:
            # Try to find reviews section by multiple selectors
            reviews_selectors = [
                "#reviews-section",
                "#customerReviews",
                "[data-hook='reviews-section']",
                "section[id*='reviews']",
                "div[id*='reviews']"
            ]
            
            reviews_element = None
            for selector in reviews_selectors:
                try:
                    if selector.startswith("#"):
                        # ID selector
                        element_id = selector[1:]
                        reviews_element = self.driver.find_element(By.ID, element_id)
                    elif selector.startswith("["):
                        # Attribute selector - use XPath or CSS
                        reviews_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    else:
                        # Tag selector with attribute
                        reviews_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if reviews_element:
                        break
                except:
                    continue
            
            # If reviews section found, scroll to it
            if reviews_element:
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'start'});", reviews_element)
                time.sleep(2)
            else:
                # Fallback: scroll to bottom of page
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
            
            # Scroll incrementally to load lazy-loaded reviews
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            scroll_attempts = 0
            max_scroll_attempts = 3
            
            while scroll_attempts < max_scroll_attempts:
                # Scroll down a bit more
                self.driver.execute_script("window.scrollBy(0, 800);")
                time.sleep(1)
                
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
                scroll_attempts += 1
            
            # Small delay for any remaining dynamic content
            time.sleep(1)
            
        except Exception:
            # If scrolling fails, just scroll to bottom as fallback
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
    
    def extract_products(self, product_url):
        """
        Extract individual reviews from current Amazon product page (reviews section at bottom).
        Based on scrapehero reference implementation patterns.
        
        Args:
            product_url: Product URL (already on this page, no navigation needed)
            
        Returns:
            DataFrame with reviews
        """
        try:
            # Already on product page, no need to navigate
            # Ensure we're scrolled to reviews section
            self._scroll_to_reviews_section()
            
            # Get page source after scrolling
            page_source = self.driver.page_source
            
            # Check for bot detection/blocked page
            if "To discuss automated access to Amazon data please contact" in page_source:
                raise CustomException(
                    f"Product page {product_url} was blocked by Amazon. Please try using better proxies or reduce request frequency.",
                    sys
                )
            
            # Additional scroll to ensure all lazy-loaded reviews are visible
            self.scroll_to_load_reviews()
            
            # Re-fetch page source after additional scrolling
            page_source = self.driver.page_source
            html = bs(page_source, "html.parser")
            
            # Find review containers - Amazon uses data-hook="review" (same on product page)
            review_containers = html.find_all("div", {"data-hook": "review"})
            
            # If no reviews found with data-hook, try alternative selectors
            if not review_containers:
                # Try finding reviews in reviews section container
                reviews_section = html.find("div", {"id": "reviews-section"}) or html.find("div", {"id": "customerReviews"})
                if reviews_section:
                    review_containers = reviews_section.find_all("div", {"data-hook": "review"})
            
            # Fallback: try any div with review-related class
            if not review_containers:
                review_containers = html.find_all("div", class_=lambda x: x and "review" in str(x).lower())
            
            reviews = []
            
            for container in review_containers:
                try:
                    # Extract rating - improved parsing like reference
                    rating_elem = container.find("span", {"class": "a-icon-alt"})
                    if rating_elem:
                        rating_text = rating_elem.text.strip()
                        # Reference pattern: split ' out of' and take first part
                        if ' out of' in rating_text:
                            rating = rating_text.split(' out of')[0].strip()
                        else:
                            # Fallback: extract number
                            rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                            rating = rating_match.group(1) if rating_match else "No rating Given"
                    else:
                        # Try finding rating in i tag with class containing "star"
                        rating_i = container.find("i", class_=lambda x: x and "star" in str(x).lower())
                        if rating_i:
                            rating_text = rating_i.get("class", [""])[0] if rating_i.get("class") else ""
                            rating_match = re.search(r'(\d+)', rating_text)
                            rating = rating_match.group(1) if rating_match else "No rating Given"
                        else:
                            rating = "No rating Given"
                    
                    # Extract review title - improved extraction
                    title_elem = container.find("a", {"data-hook": "review-title"})
                    title = ""
                    if title_elem:
                        # Get all spans and extract text
                        title_spans = title_elem.find_all("span")
                        if title_spans:
                            title = " ".join([span.text.strip() for span in title_spans if span.text.strip()])
                        else:
                            title = title_elem.text.strip()
                    
                    # Extract comment/review text - improved extraction like reference
                    comment_elem = container.find("span", {"data-hook": "review-body"})
                    comment = ""
                    if comment_elem:
                        # Get all spans inside review-body (nested structure)
                        comment_spans = comment_elem.find_all("span")
                        if comment_spans:
                            # Get the innermost span with actual text
                            for span in reversed(comment_spans):
                                span_text = span.text.strip()
                                if span_text and len(span_text) > 10:  # Likely the actual review text
                                    comment = span_text
                                    break
                            if not comment:
                                comment = " ".join([s.text.strip() for s in comment_spans if s.text.strip()])
                        else:
                            comment = comment_elem.text.strip()
                    else:
                        comment = "No comment Given"
                    
                    # Combine title and comment if both exist
                    if title and comment:
                        comment = f"{title}. {comment}"
                    elif title:
                        comment = title
                    
                    # Extract reviewer name - improved extraction
                    name_elem = container.find("span", {"class": "a-profile-name"})
                    if not name_elem:
                        name_elem = container.find("div", {"class": "a-profile-name"})
                    if not name_elem:
                        # Try alternative selector
                        name_elem = container.find("span", class_=lambda x: x and "profile-name" in str(x).lower())
                    name = name_elem.text.strip() if name_elem else "No Name given"
                    
                    # Extract date - improved parsing like reference
                    date_elem = container.find("span", {"data-hook": "review-date"})
                    if date_elem:
                        date_text = date_elem.text.strip()
                        # Reference pattern: extract date after "on " 
                        if "on " in date_text:
                            date = date_text.split("on ")[-1].strip()
                        else:
                            date = date_text
                    else:
                        date_elem = container.find("span", {"class": "a-size-base a-color-secondary review-date"})
                        if date_elem:
                            date_text = date_elem.text.strip()
                            if "on " in date_text:
                                date = date_text.split("on ")[-1].strip()
                            else:
                                date = date_text
                        else:
                            date = "No Date given"
                    
                    review_dict = {
                        "Product Name": self.product_title,
                        "Over_All_Rating": self.product_rating_value,
                        "Price": self.product_price,
                        "Date": date,
                        "Rating": rating,
                        "Name": name,
                        "Comment": comment,
                    }
                    reviews.append(review_dict)
                    
                except Exception as e:
                    # Skip malformed reviews but log for debugging
                    continue
            
            if not reviews:
                return pd.DataFrame()
            
            review_data = pd.DataFrame(
                reviews,
                columns=[
                    "Product Name",
                    "Over_All_Rating",
                    "Price",
                    "Date",
                    "Rating",
                    "Name",
                    "Comment",
                ],
            )
            
            return review_data
            
        except CustomException:
            raise
        except Exception as e:
            raise CustomException(e, sys)

