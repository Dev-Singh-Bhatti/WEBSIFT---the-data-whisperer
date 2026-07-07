from selenium.common.exceptions import TimeoutException
from src.exception import CustomException
from bs4 import BeautifulSoup as bs
import pandas as pd
import os, sys
import json
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
                    self.scaled_sleep(3)  # Wait for page to load
                    
                    # Check if page loaded successfully
                    if "ERR_" in self.driver.page_source or "can't be reached" in self.driver.page_source.lower():
                        if attempt < max_retries - 1:
                            self.scaled_sleep(2 * (attempt + 1))
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
                        self.scaled_sleep(2 * (attempt + 1))
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
            self.scaled_sleep(2)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self.scaled_sleep(2)
            
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
                            # Preserve query string while removing fragment
                            clean_href = href.split("#")[0]
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
                        # Preserve query string while removing fragment
                        clean_href = href.split("#")[0]
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
    
    def _normalize_text(self, value):
        """Normalize noisy whitespace from dynamic HTML fragments."""
        if value is None:
            return ""
        normalized = str(value).replace("\xa0", " ")
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _parse_rating_text(self, text):
        """Extract a valid 0-5 rating from a text fragment."""
        normalized = self._normalize_text(text).replace(",", "")
        if not normalized:
            return None
        for match in re.findall(r"\d+(?:\.\d+)?", normalized):
            try:
                value = float(match)
            except ValueError:
                continue
            if 0 < value <= 5:
                return match
        return None

    def _parse_price_text(self, text):
        """Extract and normalize a product price from text."""
        normalized = self._normalize_text(text)
        if not normalized:
            return None

        normalized_no_commas = normalized.replace(",", "")
        inr_match = re.search(r"(?:₹|rs\.?|inr)\s*(\d+(?:\.\d+)?)", normalized_no_commas, re.IGNORECASE)
        if inr_match:
            return f"INR {inr_match.group(1)}"

        generic_match = re.search(r"\b(\d{2,}(?:\.\d+)?)\b", normalized_no_commas)
        if generic_match:
            return generic_match.group(1)

        return None

    def _extract_product_info_from_ld_json(self, html):
        """
        Extract product metadata from JSON-LD blocks.
        Flipkart's Product payload is more stable than rotating class selectors.
        """
        product_info = {"title": None, "price": None, "rating": None}
        scripts = html.find_all("script", {"type": "application/ld+json"})

        for script in scripts:
            payload = script.string or script.get_text()
            if not payload:
                continue

            try:
                parsed_payload = json.loads(payload)
            except json.JSONDecodeError:
                continue

            candidates = []
            if isinstance(parsed_payload, list):
                candidates.extend(parsed_payload)
            elif isinstance(parsed_payload, dict):
                if isinstance(parsed_payload.get("@graph"), list):
                    candidates.extend(parsed_payload["@graph"])
                else:
                    candidates.append(parsed_payload)

            for item in candidates:
                if not isinstance(item, dict):
                    continue

                item_type = item.get("@type")
                item_types = item_type if isinstance(item_type, list) else [item_type]
                normalized_types = [self._normalize_text(t).lower() for t in item_types if t]
                looks_like_product = "product" in normalized_types or ("offers" in item and "name" in item)
                if not looks_like_product:
                    continue

                if not product_info["title"] and item.get("name"):
                    product_info["title"] = self._normalize_text(item.get("name"))

                if not product_info["price"]:
                    offers = item.get("offers")
                    if isinstance(offers, list) and offers:
                        offers = offers[0]
                    if isinstance(offers, dict):
                        price = offers.get("price")
                        currency = self._normalize_text(offers.get("priceCurrency"))
                        if price is not None:
                            price_text = self._normalize_text(price)
                            if currency.upper() == "INR":
                                product_info["price"] = f"INR {price_text}"
                            elif currency:
                                product_info["price"] = f"{currency.upper()} {price_text}"
                            else:
                                product_info["price"] = price_text

                if not product_info["rating"]:
                    aggregate = item.get("aggregateRating")
                    if isinstance(aggregate, dict):
                        parsed_rating = self._parse_rating_text(aggregate.get("ratingValue"))
                        if parsed_rating:
                            product_info["rating"] = parsed_rating

                if all(product_info.values()):
                    return product_info

        return product_info

    def _create_product_fallback_dataframe(self, reason):
        """Return one product row even when no review rows are parsed."""
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

    def _extract_review_from_card(self, card):
        """
        Parse one Flipkart review card (div.fWi7J_) into output schema.
        Current page structure surfaces ordered text tokens in div[dir='auto'].
        """
        card_text = self._normalize_text(card.get_text(" ", strip=True))
        if not card_text:
            return None

        lower_text = card_text.lower()
        if (
            "ratings and reviews" in lower_text
            or "user reviews sorted by" in lower_text
            or re.search(r"\bratings?\s+and\s+\d[\d,]*\s+reviews?\b", lower_text)
        ):
            return None

        raw_tokens = []
        for token_div in card.select("div[dir='auto']"):
            token = self._normalize_text(token_div.get_text(" ", strip=True))
            if token:
                raw_tokens.append(token)

        tokens = []
        for token in raw_tokens:
            if not tokens or token != tokens[-1]:
                tokens.append(token)

        if not tokens:
            return None
        if len(tokens) == 1 and re.fullmatch(r"\+\d+", tokens[0]):
            return None

        month_pattern = r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\b"
        strict_rating_pattern = re.compile(r"^[1-5](?:\.\d)?$")

        def _is_meta(token):
            token_lower = token.lower()
            return (
                token in {"•", "·", "-", "|"}
                or token_lower.startswith("review for:")
                or "verified purchase" in token_lower
                or "helpful" in token_lower
                or re.fullmatch(r"\+?\d+", token) is not None
            )

        rating = "No rating Given"
        rating_index = -1
        for idx, token in enumerate(tokens[:4]):
            token_clean = token.strip()
            if strict_rating_pattern.fullmatch(token_clean):
                rating = token_clean
                rating_index = idx
                break
            parsed_rating = self._parse_rating_text(token_clean)
            if parsed_rating:
                rating = parsed_rating
                rating_index = idx
                break

        date = "No Date given"
        date_index = -1
        for idx in range(len(tokens) - 1, -1, -1):
            token = tokens[idx]
            token_lower = token.lower()
            if re.search(month_pattern, token_lower) or re.search(r"\b(?:19|20)\d{2}\b", token):
                date = token.lstrip("· ").strip()
                date_index = idx
                break

        title = None
        title_index = -1
        start_idx = rating_index + 1 if rating_index >= 0 else 0
        for idx in range(start_idx, len(tokens)):
            token = tokens[idx]
            token_lower = token.lower()
            if _is_meta(token):
                continue
            if idx == date_index:
                continue
            if re.search(month_pattern, token_lower):
                continue
            if len(token) < 3 or len(token) > 120:
                continue
            if len(token.split()) > 12:
                continue
            title = token
            title_index = idx
            break

        comment = "No comment Given"
        comment_index = -1
        comment_candidates = []
        for idx, token in enumerate(tokens):
            token_lower = token.lower()
            if _is_meta(token):
                continue
            if idx in {rating_index, title_index, date_index}:
                continue
            if token.startswith(","):
                continue
            if re.search(month_pattern, token_lower):
                continue
            if self._parse_rating_text(token):
                continue
            if len(token) >= 15 and re.search(r"[a-zA-Z]", token):
                comment_candidates.append((idx, token))

        if comment_candidates:
            comment_index, comment = max(comment_candidates, key=lambda item: len(item[1]))

        name = "No Name given"
        scan_end = date_index if date_index >= 0 else len(tokens)
        for idx in range(scan_end - 1, -1, -1):
            token = tokens[idx]
            token_lower = token.lower()
            if _is_meta(token):
                continue
            if idx in {rating_index, title_index, comment_index}:
                continue
            if token.startswith(","):
                continue
            if re.search(month_pattern, token_lower):
                continue
            if re.search(r"\d", token):
                continue
            word_count = len(token.split())
            if 1 <= word_count <= 5 and len(token) <= 40:
                name = token
                break

        if not name:
            name = "No Name given"

        if title and comment != "No comment Given":
            if title.lower() not in comment.lower():
                comment = f"{title} {comment}"
        elif title and comment == "No comment Given":
            comment = title

        # Final quality gates to avoid summary/distribution widgets being parsed as reviews.
        comment_lower = comment.lower()
        if "ratings and" in comment_lower and "reviews" in comment_lower:
            return None
        if comment == "No comment Given" and rating == "No rating Given":
            return None
        if date == "No Date given" and "verified purchase" not in lower_text:
            return None
        if name == "No Name given" and comment == "No comment Given":
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

    def extract_reviews(self, product_link):
        """
        Extract review link and product details from Flipkart product page.

        Args:
            product_link: Product URL path

        Returns:
            Review page URL (or product URL fallback) or None when page load fails
        """
        try:
            if product_link.startswith("http"):
                product_url = product_link
            else:
                product_url = f"https://www.flipkart.com{product_link}"

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self._apply_rate_limit()
                    self.driver.get(product_url)
                    self.scaled_sleep(3)

                    page_source = self.driver.page_source
                    if "ERR_" in page_source or "can't be reached" in page_source.lower():
                        if attempt < max_retries - 1:
                            self.scaled_sleep(2 * (attempt + 1))
                            continue
                        return None
                    break
                except Exception:
                    if attempt < max_retries - 1:
                        self.scaled_sleep(2 * (attempt + 1))
                        continue
                    return None

            try:
                self.wait.until(lambda d: "flipkart" in d.page_source.lower())
            except TimeoutException:
                pass

            html = bs(self.driver.page_source, "html.parser")
            ld_product_info = self._extract_product_info_from_ld_json(html)

            self.product_title = ld_product_info.get("title") or "Unknown Product"
            self.product_price = ld_product_info.get("price") or "N/A"
            self.product_rating_value = ld_product_info.get("rating") or "N/A"

            if self.product_title == "Unknown Product":
                title_elem = html.find("span", {"class": "B_NuCI"}) or html.find("h1")
                if title_elem:
                    self.product_title = self._normalize_text(title_elem.get_text(strip=True))
                else:
                    title_tag = html.find("title")
                    if title_tag:
                        self.product_title = self._normalize_text(title_tag.get_text(strip=True).split("|")[0])

            if self.product_rating_value == "N/A":
                for selector in (
                    ("span", {"id": lambda x: x and "productRating" in str(x), "class": "CjyrHS"}),
                    ("div", {"class": "_3LWZlK"}),
                    ("div", {"class": "_2d4LTz"}),
                ):
                    rating_elem = html.find(selector[0], selector[1])
                    if rating_elem:
                        parsed_rating = self._parse_rating_text(rating_elem.get_text(strip=True))
                        if parsed_rating:
                            self.product_rating_value = parsed_rating
                            break

            if self.product_price == "N/A":
                for selector in (
                    ("div", {"class": "_30jeq3"}),
                    ("div", {"class": "_25b18c"}),
                    ("div", {"class": "hZ3P6w"}),
                ):
                    price_elem = html.find(selector[0], selector[1])
                    if price_elem:
                        parsed_price = self._parse_price_text(price_elem.get_text(strip=True))
                        if parsed_price:
                            self.product_price = parsed_price
                            break

            review_link = None
            for link in html.find_all("a", href=True):
                href = link.get("href", "")
                if href and "/product-reviews/" in href:
                    review_link = href.split("#")[0]
                    break

            if not review_link:
                try:
                    review_link_js = self.driver.execute_script(
                        "const a=document.querySelector('a[href*=\"/product-reviews/\"]');"
                        "return a ? a.getAttribute('href') : null;"
                    )
                    if review_link_js:
                        review_link = review_link_js
                except Exception:
                    pass

            if not review_link:
                current_url = self.driver.current_url
                parsed_url = urlparse(current_url)
                query_params = parse_qs(parsed_url.query)
                product_pid = query_params.get("pid", [None])[0]
                if not product_pid:
                    path_match = re.search(r"/p/([^/?]+)", parsed_url.path)
                    if path_match:
                        product_pid = path_match.group(1)
                if product_pid:
                    review_link = f"/product-reviews/{product_pid}?pid={product_pid}&page=1&sortOrder=MOST_HELPFUL"

            if not review_link:
                return self.driver.current_url

            if review_link.startswith("http"):
                return review_link
            if review_link.startswith("/"):
                return f"https://www.flipkart.com{review_link}"
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
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self._apply_rate_limit()
                    self.driver.get(review_url)
                    self.scaled_sleep(2)

                    page_source = self.driver.page_source
                    if "ERR_" in page_source or "can't be reached" in page_source.lower():
                        if attempt < max_retries - 1:
                            self.scaled_sleep(2 * (attempt + 1))
                            continue
                        return self._create_product_fallback_dataframe("Review page failed to load")
                    break
                except Exception:
                    if attempt < max_retries - 1:
                        self.scaled_sleep(2 * (attempt + 1))
                        continue
                    return self._create_product_fallback_dataframe("Review page request failed")

            try:
                self.wait.until(lambda d: "fWi7J_" in d.page_source or "review" in d.page_source.lower())
            except TimeoutException:
                pass

            # Faster than full-page infinite scroll while still triggering lazy review chunks.
            for _ in range(4):
                self.driver.execute_script("window.scrollBy(0, 1200);")
                self.scaled_sleep(0.6, min_sleep=0.1)

            html = bs(self.driver.page_source, "html.parser")
            review_cards = html.select("div.fWi7J_")

            if not review_cards:
                return self._create_product_fallback_dataframe("No review cards found")

            reviews = []
            seen = set()
            for card in review_cards:
                parsed_review = self._extract_review_from_card(card)
                if not parsed_review:
                    continue

                dedupe_key = (
                    parsed_review.get("Name"),
                    parsed_review.get("Date"),
                    parsed_review.get("Comment"),
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                reviews.append(parsed_review)

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
