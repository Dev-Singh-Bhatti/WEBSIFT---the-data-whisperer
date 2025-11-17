from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from src.exception import CustomException
from bs4 import BeautifulSoup as bs
import pandas as pd
import os, sys
import time
import re
from urllib.parse import quote, urlparse, parse_qs
from src.scrapper.base_scraper import BaseScraper


class FlipkartScraper(BaseScraper):
    platform_name = "flipkart"
    
    def scrape_product_urls(self, product_name: str) -> list:
        """
        Scrape product URLs from Flipkart search results.
        
        Args:
            product_name: Product name to search for
            
        Returns:
            List of product URL paths
        """
        try:
            encoded_query = quote(product_name)
            search_url = f"https://www.flipkart.com/search?q={encoded_query}"
            
            # Retry logic for network errors
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.driver.get(search_url)
                    time.sleep(3)  # Wait for page to load
                    
                    # Check if page loaded successfully
                    if "ERR_" in self.driver.page_source or "can't be reached" in self.driver.page_source.lower():
                        if attempt < max_retries - 1:
                            time.sleep(2 * (attempt + 1))
                            continue
                        else:
                            raise CustomException(
                                f"Failed to load Flipkart search page after {max_retries} attempts. "
                                f"URL: {search_url}. This may indicate network issues or Flipkart blocking requests.",
                                sys
                            )
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(2 * (attempt + 1))
                        continue
                    else:
                        raise
            
            # Wait for search results to load
            try:
                self.wait.until(lambda d: "container" in d.page_source or "search" in d.page_source.lower())
            except TimeoutException:
                pass  # Continue even if explicit wait fails
            
            # Scroll to load more products
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            page_source = self.driver.page_source
            html = bs(page_source, "html.parser")
            
            product_urls = []
            
            # Flipkart product links are typically in containers with class patterns like:
            # _1AtVbE, _4rR01T, or directly in anchor tags with /p/ pattern
            # Try finding product containers first
            product_containers = html.find_all("div", class_=lambda x: x and ("_1AtVbE" in str(x) or "_13oc-S" in str(x) or "_2kHMtA" in str(x)))
            
            if product_containers:
                for container in product_containers:
                    link_elem = container.find("a", href=True)
                    if link_elem:
                        href = link_elem.get("href", "")
                        if href and "/p/" in href and "/product-reviews/" not in href:
                            # Normalize relative URLs
                            if not href.startswith("http"):
                                if not href.startswith("/"):
                                    href = "/" + href
                            # Extract clean product URL (remove query params and fragment)
                            clean_href = href.split("?")[0].split("#")[0]
                            if clean_href not in product_urls:
                                product_urls.append(clean_href)
            
            # Fallback: find all links and filter
            if not product_urls:
                product_links = html.find_all("a", href=True)
                for link in product_links:
                    href = link.get("href", "")
                    # Filter for product URLs (contain /p/ but not /product-reviews/)
                    if href and "/p/" in href and "/product-reviews/" not in href:
                        # Normalize relative URLs
                        if not href.startswith("http"):
                            if not href.startswith("/"):
                                href = "/" + href
                        # Extract clean product URL (remove query params and fragment)
                        clean_href = href.split("?")[0].split("#")[0]
                        if clean_href not in product_urls:
                            product_urls.append(clean_href)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_urls = []
            for url in product_urls:
                if url not in seen:
                    seen.add(url)
                    unique_urls.append(url)
            
            return unique_urls[:self.no_of_products * 2]  # Get extra URLs in case some don't have reviews
            
        except CustomException:
            raise
        except Exception as e:
            raise CustomException(e, sys)
    
    def extract_reviews(self, product_link):
        """
        Extract review link and product details from Flipkart product page.
        
        Args:
            product_link: Product URL path
            
        Returns:
            Review link URL or None if no reviews found
        """
        try:
            # Construct full URL if needed
            if product_link.startswith("http"):
                product_url = product_link
            else:
                product_url = f"https://www.flipkart.com{product_link}"
            
            # Retry logic for network errors
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.driver.get(product_url)
                    time.sleep(3)  # Wait for product page to load
                    
                    # Check if page loaded successfully
                    if "ERR_" in self.driver.page_source or "can't be reached" in self.driver.page_source.lower():
                        if attempt < max_retries - 1:
                            time.sleep(2 * (attempt + 1))
                            continue
                        else:
                            return None  # Skip this product if it fails to load
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(2 * (attempt + 1))
                        continue
                    else:
                        return None  # Skip this product on persistent errors
            
            # Wait for product page content
            try:
                self.wait.until(lambda d: "B_NuCI" in d.page_source or "product" in d.page_source.lower())
            except TimeoutException:
                pass  # Continue parsing even if explicit wait fails
            
            page_source = self.driver.page_source
            html = bs(page_source, "html.parser")
            
            # Extract product title - try multiple selectors
            title_elem = html.find("span", {"class": "B_NuCI"}) or html.find("h1", {"class": "yhB1nd"})
            if not title_elem:
                title_elem = html.find("h1")
            if title_elem:
                self.product_title = title_elem.get_text(strip=True)
            else:
                # Fallback: try to get from title tag
                title_tag = html.find("title")
                if title_tag:
                    self.product_title = title_tag.get_text(strip=True).split("|")[0].strip()
                else:
                    self.product_title = "Unknown Product"
            
            # Extract overall rating - try multiple selectors
            rating_elem = html.find("div", {"class": "_3LWZlK"}) or html.find("div", class_=lambda x: x and "LWZlK" in x)
            if not rating_elem:
                rating_elem = html.find("div", {"class": "_2d4LTz"})
            if not rating_elem:
                # Try finding by text pattern
                rating_divs = html.find_all("div", string=lambda text: text and (text.strip().replace(".", "").isdigit() and len(text.strip()) <= 3))
                if rating_divs:
                    rating_elem = rating_divs[0]
            
            if rating_elem:
                self.product_rating_value = rating_elem.get_text(strip=True)
            else:
                self.product_rating_value = "N/A"
            
            # Extract price - try multiple selectors
            price_elem = html.find("div", {"class": "_30jeq3"}) or html.find("div", class_=lambda x: x and "30jeq3" in x)
            if not price_elem:
                price_elem = html.find("div", {"class": "_25b18c"})
            if price_elem:
                self.product_price = price_elem.get_text(strip=True)
            else:
                self.product_price = "N/A"
            
            # Find reviews link - try multiple approaches
            review_link = None
            
            # Method 1: Look for review links in anchor tags with href containing /product-reviews/
            review_links = html.find_all("a", href=True)
            for link in review_links:
                href = link.get("href", "")
                if href and "/product-reviews/" in href:
                    review_link = href
                    break
            
            # Method 1b: Look for "All Reviews" link by text
            if not review_link:
                review_text_links = html.find_all("a", href=True, string=lambda text: text and ("review" in text.lower() or "rating" in text.lower() or "all" in text.lower()))
                if review_text_links:
                    for link in review_text_links:
                        href = link.get("href", "")
                        if href and "/product-reviews/" in href:
                            review_link = href
                            break
            
            # Method 2: Look for reviews section with clickable rating
            if not review_link:
                reviews_section = html.find("div", {"class": "_3UAT2v"}) or html.find("div", class_=lambda x: x and "UAT2v" in x)
                if reviews_section:
                    review_link_elem = reviews_section.find("a", href=True)
                    if review_link_elem:
                        review_link = review_link_elem.get("href")
            
            # Method 3: Look for rating div that's inside a clickable link
            if not review_link:
                rating_section = html.find("div", {"class": "_2d4LTz"}) or html.find("div", class_=lambda x: x and "d4LTz" in x)
                if rating_section:
                    parent_link = rating_section.find_parent("a", href=True)
                    if parent_link:
                        href = parent_link.get("href", "")
                        if "/product-reviews/" in href:
                            review_link = href
            
            # Method 4: Use JavaScript to find review link from page (more reliable)
            if not review_link:
                try:
                    # Try to find review link using JavaScript - check all anchor tags
                    js_code = """
                    var links = document.querySelectorAll('a[href*="/product-reviews/"]');
                    if (links.length > 0) {
                        return links[0].href;
                    }
                    return null;
                    """
                    review_link_js = self.driver.execute_script(js_code)
                    if review_link_js:
                        review_link = review_link_js
                except:
                    pass
            
            # Method 5: Construct review URL from product URL or current page URL
            if not review_link:
                # Get the actual current URL (may have been redirected)
                current_url = self.driver.current_url
                
                # Try to extract product ID from current URL
                if "/p/" in current_url:
                    # Format: https://www.flipkart.com/product-name/p/productid?pid=xxx
                    url_parts = current_url.split("/p/")[-1].split("?")[0]
                    # Handle URLs like: product-name/p/productid or just productid
                    parts = url_parts.split("/")
                    if len(parts) > 1:
                        product_id = parts[-1]  # Last part is usually the ID
                    else:
                        product_id = url_parts
                    
                    if product_id:
                        review_link = f"/product-reviews/{product_id}?page=1&sortOrder=MOST_HELPFUL"
                elif "pid=" in current_url:
                    # Alternative format with pid parameter
                    parsed = urlparse(current_url)
                    params = parse_qs(parsed.query)
                    if "pid" in params:
                        product_id = params["pid"][0]
                        review_link = f"/product-reviews/{product_id}?page=1&sortOrder=MOST_HELPFUL"
            
            if not review_link:
                return None
            
            # Return full review URL
            if review_link.startswith("http"):
                return review_link
            elif review_link.startswith("/"):
                return f"https://www.flipkart.com{review_link}"
            else:
                return f"https://www.flipkart.com/{review_link}"
                
        except CustomException:
            raise
        except Exception as e:
            raise CustomException(e, sys)
    
    def extract_products(self, review_url):
        """
        Extract individual reviews from Flipkart review page.
        
        Args:
            review_url: Full URL to the reviews page
            
        Returns:
            DataFrame with reviews
        """
        try:
            # Retry logic for network errors
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.driver.get(review_url)
                    time.sleep(2)  # Wait for review page to load
                    
                    # Check if page loaded successfully
                    if "ERR_" in self.driver.page_source or "can't be reached" in self.driver.page_source.lower():
                        if attempt < max_retries - 1:
                            time.sleep(2 * (attempt + 1))
                            continue
                        else:
                            return pd.DataFrame()  # Return empty if review page fails
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(2 * (attempt + 1))
                        continue
                    else:
                        return pd.DataFrame()  # Return empty on persistent errors
            
            # Wait for review content to appear
            try:
                self.wait.until(lambda d: "review" in d.page_source.lower() or "rating" in d.page_source.lower())
            except TimeoutException:
                pass  # Continue parsing even if explicit wait fails
            
            # Scroll to load more reviews
            self.scroll_to_load_reviews()
            time.sleep(1)  # Brief wait after scrolling
            
            # Click "Read More" buttons to expand reviews
            try:
                # Try multiple class patterns for "Read More" buttons
                read_more_selectors = ["_1EPkIx", "t-ZTKy", "_2ryqvH"]
                for selector in read_more_selectors:
                    try:
                        read_more_buttons = self.driver.find_elements(By.CLASS_NAME, selector)
                        for button in read_more_buttons[:15]:  # Limit to avoid too many clicks
                            try:
                                if button.is_displayed():
                                    button.click()
                                    time.sleep(0.3)
                            except:
                                pass
                        if read_more_buttons:
                            break
                    except:
                        continue
            except:
                pass
            
            page_source = self.driver.page_source
            html = bs(page_source, "html.parser")
            
            # Find review containers - Flipkart uses various class patterns
            review_containers = []
            
            # Method 1: Try multiple known container class patterns
            container_classes = ["_3DCdKt", "_27M-vq", "_1PBCrt", "_1YokD2", "_1AtVbE", "col"]
            for class_name in container_classes:
                containers = html.find_all("div", {"class": class_name})
                if containers and len(containers) > 0:
                    # Filter to only keep containers that likely contain reviews
                    filtered = []
                    for cont in containers:
                        # Check if container has rating or review-like content
                        text = cont.get_text(strip=True)
                        has_rating = cont.find("div", class_=lambda x: x and ("LWZlK" in str(x) or "d4LTz" in str(x)))
                        has_text = len(text) > 50 and any(word in text.lower() for word in ["star", "rating", "review"])
                        if has_rating or has_text:
                            filtered.append(cont)
                    if filtered:
                        review_containers = filtered
                        break
            
            # Method 2: Use JavaScript to find review containers (more reliable)
            if not review_containers:
                try:
                    js_code = """
                    var containers = [];
                    // Try to find divs that contain rating elements
                    var ratingDivs = document.querySelectorAll('div[class*="LWZlK"], div[class*="d4LTz"]');
                    for (var i = 0; i < ratingDivs.length; i++) {
                        var parent = ratingDivs[i].closest('div[class*="_"], div[class*="col"]');
                        if (parent && parent.textContent.trim().length > 50) {
                            if (containers.indexOf(parent) === -1) {
                                containers.push(parent);
                            }
                        }
                    }
                    // If no ratings found, look for divs with review-like structure
                    if (containers.length === 0) {
                        var allDivs = document.querySelectorAll('div[class*="_"]');
                        for (var i = 0; i < allDivs.length; i++) {
                            var div = allDivs[i];
                            var text = div.textContent.trim();
                            if (text.length > 100 && (text.includes('star') || text.includes('rating') || text.includes('ago'))) {
                                if (containers.indexOf(div) === -1) {
                                    containers.push(div);
                                }
                            }
                        }
                    }
                    return containers.length;
                    """
                    container_count = self.driver.execute_script(js_code)
                    if container_count and container_count > 0:
                        # Get the actual containers
                        js_get_containers = """
                        var containers = [];
                        var ratingDivs = document.querySelectorAll('div[class*="LWZlK"], div[class*="d4LTz"]');
                        for (var i = 0; i < ratingDivs.length; i++) {
                            var parent = ratingDivs[i].closest('div[class*="_"], div[class*="col"]');
                            if (parent && parent.textContent.trim().length > 50) {
                                if (containers.indexOf(parent) === -1) {
                                    containers.push(parent);
                                }
                            }
                        }
                        if (containers.length === 0) {
                            var allDivs = document.querySelectorAll('div[class*="_"]');
                            for (var i = 0; i < allDivs.length; i++) {
                                var div = allDivs[i];
                                var text = div.textContent.trim();
                                if (text.length > 100 && (text.includes('star') || text.includes('rating') || text.includes('ago'))) {
                                    if (containers.indexOf(div) === -1) {
                                        containers.push(div);
                                    }
                                }
                            }
                        }
                        return containers;
                        """
                        # We'll parse from page source after JS execution
                        time.sleep(1)  # Wait for any dynamic updates
                        page_source = self.driver.page_source
                        html = bs(page_source, "html.parser")
                except:
                    pass
            
            # Method 3: Find by structure - look for divs containing both rating and comment patterns
            if not review_containers:
                all_divs = html.find_all("div", class_=True)
                for div in all_divs:
                    classes = div.get("class", [])
                    class_str = " ".join(classes) if isinstance(classes, list) else str(classes)
                    text = div.get_text(strip=True)
                    
                    # Check if it looks like a review container
                    has_rating_elem = div.find("div", class_=lambda x: x and ("LWZlK" in str(x) or "d4LTz" in str(x) or "star" in str(x).lower()))
                    has_comment_elem = div.find("div", class_=lambda x: x and ("qwjRop" in str(x) or "6K-7Mn" in str(x)))
                    has_review_text = len(text) > 50 and any(word in text.lower() for word in ["star", "rating", "review", "ago", "day", "month"])
                    
                    if (has_rating_elem or has_comment_elem or has_review_text) and len(class_str) > 3:
                        # Check if it's not a wrapper/parent container (avoid duplicates)
                        parent_has_review = div.find_parent("div", class_=True)
                        if not (parent_has_review and any(c in str(parent_has_review.get("class", [])) for c in ["_1AtVbE", "_13oc-S", "_2kHMtA"])):
                            review_containers.append(div)
            
            # Method 4: Look for specific review item structure
            if not review_containers:
                # Try to find by looking for divs that contain both name and rating/comment patterns
                rating_divs = html.find_all("div", class_=lambda x: x and ("LWZlK" in str(x) or "d4LTz" in str(x)))
                for rating_div in rating_divs:
                    # Find parent container
                    parent = rating_div.find_parent("div", class_=True)
                    if parent and parent not in review_containers:
                        parent_text = parent.get_text(strip=True)
                        if len(parent_text) > 30:  # Has substantial content
                            review_containers.append(parent)
            
            # Method 5: Last resort - try to extract reviews from page structure even without specific containers
            if not review_containers:
                # Look for any divs that have a structure suggesting they're reviews
                # Pattern: div with rating-like content + text content + name-like content
                all_divs = html.find_all("div", class_=True)
                potential_reviews = []
                
                for div in all_divs:
                    div_text = div.get_text(strip=True)
                    # Must have substantial text (review length)
                    if 50 < len(div_text) < 2000:
                        # Check for review indicators
                        has_rating_indicator = any(ind in div_text.lower() for ind in ["★", "star", "rating", "out of 5"])
                        has_time_indicator = any(ind in div_text.lower() for ind in ["ago", "day", "month", "year"])
                        has_review_text = len(div_text.split()) > 10  # Multiple sentences
                        
                        if has_rating_indicator and has_review_text:
                            potential_reviews.append(div)
                
                if potential_reviews:
                    review_containers = potential_reviews[:20]  # Limit to avoid too many
            
            reviews = []
            
            for container in review_containers:
                try:
                    # Extract rating - try multiple selectors and methods
                    rating = "No rating Given"
                    
                    # Method 1: Find by class
                    rating_elem = container.find("div", {"class": "_3LWZlK"}) or container.find("div", class_=lambda x: x and "LWZlK" in str(x))
                    if not rating_elem:
                        rating_elem = container.find("div", {"class": "_2d4LTz"}) or container.find("div", class_=lambda x: x and "d4LTz" in str(x))
                    
                    # Method 2: Find by text pattern (looks for numbers like 4.0, 5, etc.)
                    if not rating_elem:
                        all_divs = container.find_all("div")
                        for div in all_divs:
                            text = div.get_text(strip=True)
                            # Check if text looks like a rating (1-5, possibly with decimal)
                            if re.match(r'^[1-5]\.?\d*$', text) or re.match(r'^[1-5]\s*★', text):
                                rating_elem = div
                                break
                    
                    # Method 3: Use JavaScript to find rating if BeautifulSoup fails
                    if not rating_elem:
                        try:
                            js_rating = """
                            var container = arguments[0];
                            var ratingDivs = container.querySelectorAll('div[class*="LWZlK"], div[class*="d4LTz"]');
                            if (ratingDivs.length > 0) {
                                return ratingDivs[0].textContent.trim();
                            }
                            // Look for text that matches rating pattern
                            var allDivs = container.querySelectorAll('div');
                            for (var i = 0; i < allDivs.length; i++) {
                                var text = allDivs[i].textContent.trim();
                                if (/^[1-5]\\.?\\d*$/.test(text) || /^[1-5]\\s*★/.test(text)) {
                                    return text;
                                }
                            }
                            return null;
                            """
                            # We can't pass container directly, so we'll extract from page source
                            # Fall back to text search
                            container_text = container.get_text()
                            rating_match = re.search(r'\b([1-5]\.?\d*)\s*(?:★|star|out of)', container_text, re.IGNORECASE)
                            if rating_match:
                                rating = rating_match.group(1)
                                rating_elem = True  # Mark as found
                        except:
                            pass
                    
                    if rating_elem and rating_elem is not True:
                        rating_text = rating_elem.get_text(strip=True)
                        # Clean rating text (remove stars, keep numbers)
                        rating = rating_text.replace("★", "").replace("☆", "").strip()
                        # If still has non-numeric, try to extract just the number
                        rating_match = re.search(r'\d+\.?\d*', rating)
                        if rating_match:
                            rating = rating_match.group()
                        elif not rating_match and rating:
                            # Try to extract any number
                            rating_match = re.search(r'([1-5]\.?\d*)', rating)
                            if rating_match:
                                rating = rating_match.group(1)
                    
                    # Extract comment/review text - try multiple selectors
                    comment = "No comment Given"
                    
                    # Method 1: Find by class
                    comment_elem = container.find("div", {"class": "qwjRop"}) or container.find("div", class_=lambda x: x and "qwjRop" in str(x))
                    if not comment_elem:
                        comment_elem = container.find("div", {"class": "_6K-7Mn"}) or container.find("div", class_=lambda x: x and "6K-7Mn" in str(x))
                    
                    # Method 2: Find by text content that looks like a review (long text, not metadata)
                    if not comment_elem:
                        all_divs_in_container = container.find_all("div")
                        longest_text = ""
                        longest_elem = None
                        for div in all_divs_in_container:
                            text = div.get_text(strip=True)
                            # Look for divs with substantial text that aren't metadata
                            if len(text) > len(longest_text) and len(text) > 20:
                                # Exclude divs that are clearly metadata (name, date, rating)
                                if not any(keyword in text.lower() for keyword in ["verified purchase", "certified buyer", "days ago", "months ago", "years ago", "★", "out of", "rating:"]):
                                    # Check if it's not just a single word or short phrase
                                    words = text.split()
                                    if len(words) > 3:  # Must have multiple words
                                        longest_text = text
                                        longest_elem = div
                        
                        if longest_elem:
                            comment_elem = longest_elem
                    
                    # Method 3: Get text from container and extract review portion
                    if not comment_elem or (comment_elem and len(comment_elem.get_text(strip=True)) < 20):
                        container_text = container.get_text("\n", strip=True)
                        # Try to extract meaningful review text (skip metadata lines)
                        lines = container_text.split("\n")
                        review_lines = []
                        for line in lines:
                            line = line.strip()
                            # Skip metadata lines
                            if len(line) > 20 and not any(skip in line.lower() for skip in ["verified", "certified", "days ago", "months ago", "years ago", "★", "out of 5", "rating:", "helpful"]):
                                # Check if line looks like a review (has multiple words)
                                if len(line.split()) > 3:
                                    review_lines.append(line)
                        
                        if review_lines:
                            comment = " ".join(review_lines[:3])  # Take first few substantial lines
                    
                    if comment_elem and comment == "No comment Given":
                        # Navigate nested structure if needed
                        comment_text = comment_elem
                        nested = comment_elem.find("div", recursive=False)
                        if nested and nested.get_text(strip=True):
                            nested2 = nested.find("div", recursive=False)
                            if nested2 and nested2.get_text(strip=True):
                                comment_text = nested2
                            else:
                                comment_text = nested
                        
                        comment = comment_text.get_text(strip=True)
                    
                    # Extract reviewer name - try multiple selectors
                    name = "No Name given"
                    name_elem = container.find("p", {"class": "_2sc7ZR"}) or container.find("p", class_=lambda x: x and "sc7ZR" in str(x))
                    if not name_elem:
                        name_elem = container.find("p", {"class": "_3LYOAd"}) or container.find("p", class_=lambda x: x and "LYOAd" in str(x))
                    if name_elem:
                        name = name_elem.get_text(strip=True)
                    
                    # Extract date - try multiple selectors
                    date = "No Date given"
                    date_elem = container.find("p", {"class": "_2mcZGG"}) or container.find("p", class_=lambda x: x and "mcZGG" in str(x))
                    if not date_elem:
                        # Try finding date patterns in all paragraphs
                        all_ps = container.find_all("p")
                        for p in all_ps:
                            text = p.get_text(strip=True)
                            # Look for date-like patterns
                            if any(keyword in text.lower() for keyword in ["ago", "day", "month", "year", "202", "jan", "feb", "mar"]):
                                date_elem = p
                                break
                        
                        # Fallback: try _3LYOAd (may contain date)
                        if not date_elem:
                            date_elems = container.find_all("p", {"class": "_3LYOAd"}) or container.find_all("p", class_=lambda x: x and "LYOAd" in str(x))
                            if date_elems and len(date_elems) > 1:
                                date_elem = date_elems[1]  # Usually date is second occurrence
                    
                    if date_elem:
                        date = date_elem.get_text(strip=True)
                    
                    # Only add review if it has meaningful content
                    if comment != "No comment Given" or rating != "No rating Given":
                        review_dict = {
                            "Product Name": self.product_title or "Unknown Product",
                            "Over_All_Rating": self.product_rating_value or "N/A",
                            "Price": self.product_price or "N/A",
                            "Date": date,
                            "Rating": rating,
                            "Name": name,
                            "Comment": comment,
                        }
                        reviews.append(review_dict)
                    
                except Exception as e:
                    # Skip malformed reviews
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

