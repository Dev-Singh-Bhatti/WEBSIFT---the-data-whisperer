from selenium import webdriver 
from selenium.webdriver.common.by import By 
from selenium.common.exceptions import TimeoutException
from src.exception import CustomException
from bs4 import BeautifulSoup as bs
import pandas as pd
import os, sys
import time
from selenium.webdriver.chrome.options import Options 
from urllib.parse import quote
from src.scrapper.base_scraper import BaseScraper


class ScrapeReviews(BaseScraper):
    platform_name = "myntra"
    
    def __init__(self,
                 product_name:str,
                 no_of_products:int):
        super().__init__(product_name, no_of_products)

    def scrape_product_urls(self, product_name):
        try:
            search_string = product_name.replace(" ","-")
            encoded_query = quote(search_string)
            url = f"https://www.myntra.com/{search_string}?rawQuery={encoded_query}"
            
            # Retry logic for network errors (HTTP/2 protocol errors, etc.)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Navigate to the URL
                    self.driver.get(url)
                    time.sleep(3)  # Wait for initial page load
                    
                    # Check if page loaded successfully (not an error page)
                    if "ERR_" in self.driver.page_source or "can't be reached" in self.driver.page_source.lower():
                        if attempt < max_retries - 1:
                            time.sleep(2 * (attempt + 1))  # Exponential backoff
                            continue
                        else:
                            raise CustomException(
                                f"Failed to load Myntra search page after {max_retries} attempts. "
                                f"URL: {url}. This may indicate network issues or Myntra blocking requests.",
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
                self.wait.until(lambda d: "results-base" in d.page_source or len(d.find_elements("css selector", "ul.results-base")) > 0)
            except TimeoutException:
                pass  # Continue even if explicit wait fails
            
            myntra_text = self.driver.page_source
            myntra_html = bs(myntra_text, "html.parser")
            pclass = myntra_html.findAll("ul", {"class": "results-base"})

            product_urls = []
            for i in pclass:
                href = i.find_all("a", href=True)

                for product_no in range(len(href)):
                    t = href[product_no]["href"]
                    if t and t not in product_urls:  # Avoid duplicates
                        product_urls.append(t)

            return product_urls

        except CustomException:
            raise
        except Exception as e:
            raise CustomException(e, sys)

    def extract_reviews(self, product_link):
        try:
            productLink = "https://www.myntra.com/" + product_link
            
            # Retry logic for network errors
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.driver.get(productLink)
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
                self.wait.until(lambda d: "pdp-price" in d.page_source or "index-overallRating" in d.page_source)
            except TimeoutException:
                pass  # Continue parsing even if explicit wait fails
            
            prodRes = self.driver.page_source
            prodRes_html = bs(prodRes, "html.parser")
            title_h = prodRes_html.findAll("title")

            if not title_h:
                return None
            self.product_title = title_h[0].text if title_h[0].text else "Unknown Product"

            overallRating = prodRes_html.findAll(
                "div", {"class": "index-overallRating"}
            )
            self.product_rating_value = "N/A"
            for i in overallRating:
                rating_div = i.find("div")
                if rating_div:
                    self.product_rating_value = rating_div.text
                    break
            
            price = prodRes_html.findAll("span", {"class": "pdp-price"})
            self.product_price = "N/A"
            for i in price:
                if i.text:
                    self.product_price = i.text
                    break
            
            product_reviews = prodRes_html.find(
                "a", {"class": "detailed-reviews-allReviews"}
            )

            if not product_reviews:
                return None
            return product_reviews
        except Exception as e:
            raise CustomException(e, sys)
        



    def extract_products(self, product_reviews):
        """
        Extract individual reviews from review page.
        
        Args:
            product_reviews: BeautifulSoup element containing review link (must have 'href' attribute)
        
        Returns:
            DataFrame with reviews, or empty DataFrame if no reviews found
        """
        try:
            if not product_reviews or not hasattr(product_reviews, 'get'):
                return pd.DataFrame()
            
            t2 = product_reviews.get("href")
            if not t2:
                return pd.DataFrame()
                
            Review_link = "https://www.myntra.com" + t2
            
            # Retry logic for network errors
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.driver.get(Review_link)
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
                self.wait.until(lambda d: "detailed-reviews-userReviewsContainer" in d.page_source)
            except TimeoutException:
                pass  # Continue parsing even if explicit wait fails
            
            self.scroll_to_load_reviews()
            time.sleep(1)  # Brief wait after scrolling
            
            review_page = self.driver.page_source
            review_html = bs(review_page, "html.parser")
            review = review_html.findAll(
                "div", {"class": "detailed-reviews-userReviewsContainer"}
            )

            if not review:
                return pd.DataFrame()

            user_rating = []
            user_comment = []
            user_name = []
            
            for i in review:
                ratings = i.findAll(
                    "div", {"class": "user-review-main user-review-showRating"}
                )
                comments = i.findAll(
                    "div", {"class": "user-review-reviewTextWrapper"}
                )
                names = i.findAll("div", {"class": "user-review-left"})
                
                user_rating.extend(ratings)
                user_comment.extend(comments)
                user_name.extend(names)

            if not user_rating and not user_comment:
                return pd.DataFrame()

            reviews = []
            max_len = max(len(user_rating), len(user_comment), len(user_name))
            
            for i in range(max_len):
                try:
                    if i < len(user_rating):
                        rating_elem = user_rating[i].find("span", class_="user-review-starRating")
                        rating = rating_elem.get_text().strip() if rating_elem else "No rating Given"
                    else:
                        rating = "No rating Given"
                except:
                    rating = "No rating Given"
                
                try:
                    if i < len(user_comment):
                        comment = user_comment[i].text.strip() if user_comment[i].text else "No comment Given"
                    else:
                        comment = "No comment Given"
                except:
                    comment = "No comment Given"
                
                try:
                    if i < len(user_name):
                        name_spans = user_name[i].find_all("span")
                        name = name_spans[0].text.strip() if name_spans else "No Name given"
                    else:
                        name = "No Name given"
                except:
                    name = "No Name given"
                
                try:
                    if i < len(user_name):
                        name_spans = user_name[i].find_all("span")
                        date = name_spans[1].text.strip() if len(name_spans) > 1 else "No Date given"
                    else:
                        date = "No Date given"
                except:
                    date = "No Date given"

                mydict = {
                    "Product Name": self.product_title,
                    "Over_All_Rating": self.product_rating_value,
                    "Price": self.product_price,
                    "Date": date,
                    "Rating": rating,
                    "Name": name,
                    "Comment": comment,
                }
                reviews.append(mydict)

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

        except Exception as e:
            raise CustomException(e, sys)
        
    
