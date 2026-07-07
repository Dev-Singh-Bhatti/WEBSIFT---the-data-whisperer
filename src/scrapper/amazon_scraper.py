from src.exception import CustomException
from bs4 import BeautifulSoup as bs
import pandas as pd
import os, sys
import random
import re
import logging
from urllib.parse import quote, urlparse
from typing import Optional
from src.scrapper.base_scraper import BaseScraper
from src.utils.scraping_utils import check_bot_detection
from src.config import PROXY_ENABLED, PROXY_LIST

logger = logging.getLogger(__name__)


class AmazonScraper(BaseScraper):
    platform_name = "amazon"

    def __init__(self, product_name: str, no_of_products: int, proxy: Optional[str] = None):
        """
        Initialize Amazon scraper and visit homepage first to establish session.

        Args:
            product_name: Product name to search
            no_of_products: Number of products to scrape
            proxy: Optional proxy string
        """
        selected_proxy = None
        if proxy:
            selected_proxy = proxy
        elif PROXY_ENABLED and PROXY_LIST:
            selected_proxy = random.choice(PROXY_LIST)
            logger.info(
                "Using random proxy from pool: %s",
                selected_proxy.split("@")[-1] if "@" in selected_proxy else selected_proxy,
            )

        super().__init__(product_name, no_of_products, proxy=selected_proxy)

        try:
            self._apply_rate_limit()
            self.driver.get("https://www.amazon.in")
            self.random_delay(3, 5, human_like=True)
            self.human_like_mouse_move()

            if check_bot_detection(self.driver.page_source, "amazon"):
                logger.warning("Bot detection detected on Amazon homepage")
                self.random_delay(10, 15, human_like=True)
        except Exception as e:
            logger.warning(f"Homepage visit warning: {e}")

    def _normalize_text(self, value):
        if value is None:
            return ""
        normalized = str(value).replace("\xa0", " ")
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _extract_asin_from_url(self, url):
        if not url:
            return None
        parsed = urlparse(url)
        path = parsed.path or ""
        match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?]|$)", path, flags=re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return None

    def _absolutize_amazon_url(self, href):
        href = self._normalize_text(href)
        if not href:
            return None
        if href.startswith("http"):
            return href
        if href.startswith("/"):
            return f"https://www.amazon.in{href}"
        return f"https://www.amazon.in/{href}"

    def _parse_rating_text(self, text):
        normalized = self._normalize_text(text).replace(",", "")
        if not normalized:
            return "No rating Given"
        for match in re.findall(r"\d+(?:\.\d+)?", normalized):
            try:
                value = float(match)
            except ValueError:
                continue
            if 0 < value <= 5:
                return match
        return "No rating Given"

    def _parse_price_text(self, text):
        normalized = self._normalize_text(text)
        if not normalized:
            return "N/A"
        normalized_no_commas = normalized.replace(",", "")
        inr_match = re.search(r"(?:₹|rs\.?|inr)\s*(\d+(?:\.\d+)?)", normalized_no_commas, re.IGNORECASE)
        if inr_match:
            return f"INR {inr_match.group(1)}"
        generic_match = re.search(r"\b(\d{2,}(?:\.\d+)?)\b", normalized_no_commas)
        if generic_match:
            return generic_match.group(1)
        return "N/A"

    def _create_product_fallback_dataframe(self, reason):
        return pd.DataFrame([
            {
                "Product Name": self.product_title or "Unknown Product",
                "Over_All_Rating": self.product_rating_value or "N/A",
                "Price": self.product_price or "N/A",
                "Date": "N/A",
                "Rating": "N/A",
                "Name": "N/A",
                "Comment": reason,
            }
        ])

    def _extract_review_link_from_product_page(self, html, asin):
        if asin:
            specific_see_all = html.select_one(
                f'a[data-hook="see-all-reviews-link-foot"][href*="{asin}"]'
            )
            if specific_see_all and specific_see_all.get("href"):
                return self._absolutize_amazon_url(specific_see_all.get("href"))

        generic_see_all = html.select_one('a[data-hook="see-all-reviews-link-foot"][href]')
        if generic_see_all and generic_see_all.get("href"):
            candidate = self._absolutize_amazon_url(generic_see_all.get("href"))
            if candidate and (not asin or f"/product-reviews/{asin}" in candidate):
                return candidate

        if asin:
            for anchor in html.select(f'a[href*="/product-reviews/{asin}"]'):
                href = self._normalize_text(anchor.get("href"))
                if not href:
                    continue
                if "show_all" in href or "reviewerType=all_reviews" in href:
                    return self._absolutize_amazon_url(href)

            return (
                f"https://www.amazon.in/product-reviews/{asin}/"
                "?reviewerType=all_reviews&pageNumber=1&sortBy=recent"
            )

        return None

    def _is_signin_or_block_page(self):
        title = self._normalize_text(getattr(self.driver, "title", "")).lower()
        current_url = self._normalize_text(getattr(self.driver, "current_url", "")).lower()
        source = self.driver.page_source.lower()

        if "amazon sign-in" in title or "/ap/signin" in current_url:
            return True
        if check_bot_detection(source, "amazon"):
            return True
        return False

    def _extract_review_from_container(self, container):
        rating_elem = (
            container.select_one('[data-hook="review-star-rating"]')
            or container.select_one('[data-hook="cmps-review-star-rating"]')
            or container.select_one("span.a-icon-alt")
        )
        rating = self._parse_rating_text(rating_elem.get_text(" ", strip=True) if rating_elem else "")

        title_elem = container.select_one('[data-hook="review-title"]')
        title = self._normalize_text(title_elem.get_text(" ", strip=True) if title_elem else "")
        title = re.sub(r"^\d+(?:\.\d+)?\s*out of\s*5\s*stars?\s*", "", title, flags=re.IGNORECASE)

        body_elem = container.select_one('[data-hook="review-body"]')
        body = self._normalize_text(body_elem.get_text(" ", strip=True) if body_elem else "")
        body = re.sub(r"\s*Read more\s*$", "", body, flags=re.IGNORECASE)

        name_elem = container.select_one("span.a-profile-name") or container.select_one('[data-hook="review-author"]')
        name = self._normalize_text(name_elem.get_text(" ", strip=True) if name_elem else "")
        if not name:
            name = "No Name given"

        date_elem = container.select_one('[data-hook="review-date"]')
        date_text = self._normalize_text(date_elem.get_text(" ", strip=True) if date_elem else "")
        if date_text:
            match = re.search(r"\bon\s+(.+)$", date_text, flags=re.IGNORECASE)
            date = self._normalize_text(match.group(1) if match else date_text)
        else:
            date = "No Date given"

        comment = ""
        if title and body:
            if title.lower() in body.lower():
                comment = body
            else:
                comment = f"{title}. {body}"
        elif body:
            comment = body
        elif title:
            comment = title

        comment = self._normalize_text(comment)
        if not comment:
            comment = "No comment Given"

        # Quality gates: drop empty/metadata-only rows.
        if comment == "No comment Given" and rating == "No rating Given":
            return None
        if date == "No Date given" and name == "No Name given":
            return None

        return {
            "Product Name": self.product_title or "Unknown Product",
            "Over_All_Rating": self.product_rating_value or "N/A",
            "Price": self.product_price or "N/A",
            "Date": date,
            "Rating": rating,
            "Name": name,
            "Comment": comment,
        }

    def scrape_product_urls(self, product_name: str) -> list:
        """
        Scrape product URLs from Amazon search results.

        Args:
            product_name: Product name to search for

        Returns:
            List of canonical product URLs
        """
        try:
            encoded_query = quote(product_name)
            search_url = f"https://www.amazon.in/s?k={encoded_query}"

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self._apply_rate_limit()
                    self.driver.get(search_url)
                    self.random_delay(4, 7, human_like=True)

                    page_source = self.driver.page_source
                    if check_bot_detection(page_source, "amazon"):
                        if attempt < max_retries - 1:
                            logger.warning("Amazon search blocked/detected. Retrying...")
                            self.random_delay(8, 12, human_like=True)
                            continue
                        return []
                    break
                except Exception:
                    if attempt < max_retries - 1:
                        self.random_delay(3, 6, human_like=True)
                        continue
                    return []

            # Light scroll to trigger lazy-loaded cards without huge latency.
            for _ in range(3):
                self.driver.execute_script("window.scrollBy(0, 1200);")
                self.scaled_sleep(0.8, min_sleep=0.1)

            html = bs(self.driver.page_source, "html.parser")
            product_urls = []

            result_cards = html.select("div.s-main-slot div[data-component-type='s-search-result']")
            for card in result_cards:
                asin = self._normalize_text(card.get("data-asin"))
                if not re.fullmatch(r"[A-Z0-9]{10}", asin):
                    continue
                canonical_url = f"https://www.amazon.in/dp/{asin}"
                if canonical_url not in product_urls:
                    product_urls.append(canonical_url)

            # Fallback path when card parsing fails.
            if not product_urls:
                for anchor in html.find_all("a", href=True):
                    href = self._normalize_text(anchor.get("href"))
                    asin = self._extract_asin_from_url(href)
                    if not asin:
                        continue
                    canonical_url = f"https://www.amazon.in/dp/{asin}"
                    if canonical_url not in product_urls:
                        product_urls.append(canonical_url)

            return product_urls[: self.no_of_products * 2]

        except Exception as e:
            raise CustomException(e, sys)

    def extract_reviews(self, product_url):
        """
        Open product page and extract product metadata plus review page link.

        Args:
            product_url: Full Amazon product URL

        Returns:
            Dict with product_url/review_url/asin, or None when page fails
        """
        try:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self._apply_rate_limit()
                    self.driver.get(product_url)
                    self.random_delay(4, 7, human_like=True)

                    if check_bot_detection(self.driver.page_source, "amazon"):
                        if attempt < max_retries - 1:
                            self.random_delay(8, 12, human_like=True)
                            continue
                        return None
                    break
                except Exception:
                    if attempt < max_retries - 1:
                        self.random_delay(3, 6, human_like=True)
                        continue
                    return None

            html = bs(self.driver.page_source, "html.parser")
            current_url = self.driver.current_url or product_url
            asin = self._extract_asin_from_url(current_url) or self._extract_asin_from_url(product_url)

            title_elem = html.select_one("#productTitle") or html.select_one("h1.a-size-large")
            if title_elem:
                self.product_title = self._normalize_text(title_elem.get_text(" ", strip=True))
            else:
                title_tag = html.find("title")
                if title_tag:
                    self.product_title = self._normalize_text(title_tag.get_text(strip=True).split("|")[0])
                else:
                    self.product_title = "Unknown Product"

            rating_elem = html.select_one("#acrPopover") or html.select_one("span.a-icon-alt")
            rating_text = ""
            if rating_elem:
                rating_text = rating_elem.get("title") or rating_elem.get_text(" ", strip=True)
            self.product_rating_value = self._parse_rating_text(rating_text)
            if self.product_rating_value == "No rating Given":
                self.product_rating_value = "N/A"

            price_elem = (
                html.select_one("#corePrice_feature_div span.a-price span.a-offscreen")
                or html.select_one("span.a-price span.a-offscreen")
                or html.select_one("#priceblock_ourprice")
                or html.select_one("#priceblock_dealprice")
                or html.select_one("#priceblock_saleprice")
                or html.select_one("span.a-price-whole")
            )
            self.product_price = self._parse_price_text(price_elem.get_text(" ", strip=True) if price_elem else "")

            review_url = self._extract_review_link_from_product_page(html, asin)

            return {
                "product_url": current_url,
                "review_url": review_url,
                "asin": asin,
            }

        except CustomException:
            raise
        except Exception as e:
            raise CustomException(e, sys)

    def extract_products(self, review_data):
        """
        Extract individual reviews from Amazon review surface.

        Args:
            review_data: dict from extract_reviews (or legacy product URL str)

        Returns:
            DataFrame with reviews
        """
        try:
            if not review_data:
                return self._create_product_fallback_dataframe("Product page unavailable")

            if isinstance(review_data, dict):
                product_url = review_data.get("product_url")
                review_url = review_data.get("review_url")
            else:
                product_url = str(review_data)
                review_url = None

            loaded_target = False

            # Try dedicated review page first.
            if review_url:
                max_retries = 2
                for attempt in range(max_retries):
                    try:
                        self._apply_rate_limit()
                        self.driver.get(review_url)
                        self.scaled_sleep(3)
                        if self._is_signin_or_block_page():
                            if attempt < max_retries - 1:
                                self.random_delay(4, 7, human_like=True)
                                continue
                            break
                        loaded_target = True
                        break
                    except Exception:
                        if attempt < max_retries - 1:
                            self.random_delay(3, 6, human_like=True)
                            continue
                        break

            # Fallback to product page review section.
            if not loaded_target and product_url:
                try:
                    self._apply_rate_limit()
                    self.driver.get(product_url)
                    self.scaled_sleep(3)
                    # Trigger lazy review section render.
                    self.driver.execute_script("window.scrollBy(0, document.body.scrollHeight * 0.75);")
                    self.scaled_sleep(1.2, min_sleep=0.2)
                except Exception:
                    pass

            html = bs(self.driver.page_source, "html.parser")

            review_containers = []
            container_selectors = [
                "#cm-cr-review_list [data-hook='review']",
                "#cm-cr-dp-review-list [data-hook='review']",
                "li[data-hook='review']",
                "div[data-hook='review']",
            ]
            for selector in container_selectors:
                candidates = html.select(selector)
                if candidates:
                    review_containers = candidates
                    break

            if not review_containers:
                return self._create_product_fallback_dataframe("No review containers found")

            reviews = []
            seen = set()

            for container in review_containers:
                parsed = self._extract_review_from_container(container)
                if not parsed:
                    continue

                dedupe_key = (
                    parsed.get("Name"),
                    parsed.get("Date"),
                    parsed.get("Comment"),
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                reviews.append(parsed)

            if not reviews:
                return self._create_product_fallback_dataframe("No parseable reviews found")

            return pd.DataFrame(
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

        except CustomException:
            raise
        except Exception as e:
            raise CustomException(e, sys)
