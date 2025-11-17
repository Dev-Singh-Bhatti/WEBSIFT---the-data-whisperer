"""Service to orchestrate multi-platform scraping and generate comparison results."""

import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from typing import Dict, List, Optional, Tuple
import os
import sys
from src.exception import CustomException
from src.utils.price_normalizer import normalize_prices_column


class ComparisonService:
    """Orchestrates multi-platform scraping and generates comparison results."""
    
    def __init__(self, product_name: str, no_of_products: int = 1):
        """
        Initialize comparison service.
        
        Args:
            product_name: Product name to search
            no_of_products: Number of products to scrape per platform
        """
        self.product_name = product_name
        self.no_of_products = no_of_products
        self.results_lock = threading.Lock()
        self.results = {}
    
    def _run_scraper(self, platform: str) -> Tuple[str, Optional[pd.DataFrame]]:
        """
        Run a single platform scraper.
        
        Args:
            platform: Platform name ("myntra", "flipkart", "amazon")
            
        Returns:
            Tuple of (platform_name, DataFrame or None)
        """
        try:
            if platform == "myntra":
                from src.scrapper.scrape import ScrapeReviews
                scraper = ScrapeReviews(
                    product_name=self.product_name,
                    no_of_products=self.no_of_products
                )
            elif platform == "flipkart":
                from src.scrapper.flipkart_scraper import FlipkartScraper
                scraper = FlipkartScraper(
                    product_name=self.product_name,
                    no_of_products=self.no_of_products
                )
            elif platform == "amazon":
                from src.scrapper.amazon_scraper import AmazonScraper
                scraper = AmazonScraper(
                    product_name=self.product_name,
                    no_of_products=self.no_of_products
                )
            else:
                return (platform, None)
            
            data = scraper.get_review_data()
            return (platform, data)
            
        except Exception as e:
            # Log error but don't fail entire comparison
            return (platform, None)
    
    def scrape_all_platforms(self) -> Dict[str, pd.DataFrame]:
        """
        Scrape all platforms in parallel.
        
        Returns:
            Dictionary mapping platform names to DataFrames
        """
        platforms = ["myntra", "flipkart", "amazon"]
        results = {}
        
        # Run scrapers in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_platform = {
                executor.submit(self._run_scraper, platform): platform 
                for platform in platforms
            }
            
            for future in as_completed(future_to_platform):
                platform = future_to_platform[future]
                try:
                    result_platform, data = future.result()
                    if data is not None and not data.empty:
                        results[result_platform] = data
                except Exception as e:
                    # Continue even if one platform fails
                    continue
        
        return results
    
    def generate_comparison(self, platform_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Generate comparative summary from platform data.
        
        Args:
            platform_data: Dictionary of platform -> DataFrame
            
        Returns:
            DataFrame with comparison metrics per platform
        """
        if not platform_data:
            return pd.DataFrame()
        
        comparison_rows = []
        
        for platform, df in platform_data.items():
            # Normalize prices
            df_normalized = normalize_prices_column(df)
            
            # Get unique products (same product may appear multiple times with different reviews)
            unique_products = df_normalized["Product Name"].unique()
            
            for product_name in unique_products:
                product_df = df_normalized[df_normalized["Product Name"] == product_name]
                
                # Calculate metrics
                avg_price = product_df["Price_Numeric"].mean()
                min_price = product_df["Price_Numeric"].min()
                max_price = product_df["Price_Numeric"].max()
                
                # Rating metrics
                ratings = pd.to_numeric(product_df["Rating"], errors='coerce')
                avg_rating = ratings.mean()
                overall_rating = pd.to_numeric(product_df["Over_All_Rating"].iloc[0], errors='coerce') if len(product_df) > 0 else pd.NA
                
                # Review count
                review_count = len(product_df)
                
                # Get actual price string (first non-NA)
                price_str = product_df["Price"].iloc[0] if len(product_df) > 0 and pd.notna(product_df["Price"].iloc[0]) else "N/A"
                
                comparison_rows.append({
                    "Platform": platform,
                    "Product Name": product_name,
                    "Price": price_str,
                    "Price_Numeric": avg_price,
                    "Min_Price": min_price,
                    "Max_Price": max_price,
                    "Avg_Rating": avg_rating,
                    "Overall_Rating": overall_rating,
                    "Review_Count": review_count,
                })
        
        return pd.DataFrame(comparison_rows)
    
    def combine_all_reviews(self, platform_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Combine all reviews from all platforms into single DataFrame.
        
        Args:
            platform_data: Dictionary of platform -> DataFrame
            
        Returns:
            Combined DataFrame with all reviews
        """
        if not platform_data:
            return pd.DataFrame()
        
        all_dfs = list(platform_data.values())
        combined = pd.concat(all_dfs, axis=0, ignore_index=True)
        
        # Normalize prices
        combined = normalize_prices_column(combined)
        
        return combined
    
    def get_comparison_summary(self, comparison_df: pd.DataFrame) -> Dict:
        """
        Generate summary statistics from comparison DataFrame.
        
        Args:
            comparison_df: Comparison DataFrame from generate_comparison()
            
        Returns:
            Dictionary with summary metrics
        """
        if comparison_df.empty:
            return {}
        
        summary = {
            "total_platforms": comparison_df["Platform"].nunique(),
            "total_products": comparison_df["Product Name"].nunique(),
            "total_reviews": comparison_df["Review_Count"].sum(),
        }
        
        # Best price by platform
        valid_prices = comparison_df[comparison_df["Price_Numeric"].notna()]
        if not valid_prices.empty:
            cheapest = valid_prices.loc[valid_prices["Price_Numeric"].idxmin()]
            summary["cheapest_platform"] = cheapest["Platform"]
            summary["cheapest_price"] = cheapest["Price_Numeric"]
            summary["cheapest_product"] = cheapest["Product Name"]
        
        # Best rating by platform
        valid_ratings = comparison_df[comparison_df["Avg_Rating"].notna()]
        if not valid_ratings.empty:
            best_rated = valid_ratings.loc[valid_ratings["Avg_Rating"].idxmax()]
            summary["best_rated_platform"] = best_rated["Platform"]
            summary["best_rating"] = best_rated["Avg_Rating"]
            summary["best_rated_product"] = best_rated["Product Name"]
        
        return summary

