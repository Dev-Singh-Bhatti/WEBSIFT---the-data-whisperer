import pandas as pd
import streamlit as st 
from src.cloud_io import MongoIO
from src.constants import SESSION_PRODUCT_KEY, SESSION_PLATFORM_KEY, SUPPORTED_PLATFORMS
from src.utils.comparison_service import ComparisonService

st.set_page_config(
    "multi-platform-review-scrapper"
)

st.title("Multi-Platform Review Scraper")

# Initialize session state
if "data" not in st.session_state:
    st.session_state["data"] = False
if SESSION_PLATFORM_KEY not in st.session_state:
    st.session_state[SESSION_PLATFORM_KEY] = "myntra"
if "comparison_mode" not in st.session_state:
    st.session_state["comparison_mode"] = False

def display_comparison_results(comparison_df: pd.DataFrame, all_reviews_df: pd.DataFrame, summary: dict):
    """Display comparison results in formatted sections."""
    st.header("📊 Comparison Results")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Platforms Found", summary.get("total_platforms", 0))
    with col2:
        st.metric("Total Products", summary.get("total_products", 0))
    with col3:
        st.metric("Total Reviews", summary.get("total_reviews", 0))
    with col4:
        if "cheapest_price" in summary:
            st.metric("Best Price", f"₹{summary['cheapest_price']:.2f}")
    
    # Price comparison
    st.subheader("💰 Price Comparison")
    price_comparison = comparison_df[["Platform", "Product Name", "Price", "Price_Numeric"]].copy()
    price_comparison = price_comparison[price_comparison["Price_Numeric"].notna()]
    if not price_comparison.empty:
        st.dataframe(
            price_comparison.sort_values("Price_Numeric"),
            use_container_width=True
        )
        
        # Price chart
        if len(price_comparison) > 0:
            import plotly.express as px
            fig = px.bar(
                price_comparison,
                x="Platform",
                y="Price_Numeric",
                color="Platform",
                title="Price Comparison Across Platforms",
                labels={"Price_Numeric": "Price (₹)", "Platform": "Platform"}
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No price data available for comparison.")
    
    # Rating comparison
    st.subheader("⭐ Rating Comparison")
    rating_comparison = comparison_df[["Platform", "Product Name", "Avg_Rating", "Overall_Rating", "Review_Count"]].copy()
    rating_comparison = rating_comparison[rating_comparison["Avg_Rating"].notna()]
    if not rating_comparison.empty:
        st.dataframe(
            rating_comparison.sort_values("Avg_Rating", ascending=False),
            use_container_width=True
        )
        
        # Rating chart
        if len(rating_comparison) > 0:
            import plotly.express as px
            fig = px.bar(
                rating_comparison,
                x="Platform",
                y="Avg_Rating",
                color="Platform",
                title="Average Rating Comparison Across Platforms",
                labels={"Avg_Rating": "Average Rating", "Platform": "Platform"}
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No rating data available for comparison.")
    
    # Best deals section
    st.subheader("🏆 Best Deals")
    if "cheapest_platform" in summary:
        st.success(f"**Cheapest**: {summary['cheapest_product']} on {summary['cheapest_platform'].title()} - ₹{summary['cheapest_price']:.2f}")
    if "best_rated_platform" in summary:
        st.success(f"**Best Rated**: {summary['best_rated_product']} on {summary['best_rated_platform'].title()} - {summary['best_rating']:.2f} stars")
    
    # Full comparison table
    st.subheader("📋 Full Comparison Table")
    st.dataframe(comparison_df, use_container_width=True)
    
    # All reviews
    st.subheader("💬 All Reviews")
    st.dataframe(all_reviews_df, use_container_width=True)

def form_input():
    # Mode selection
    mode = st.radio(
        "Select Mode",
        options=["Single Platform", "Compare All Platforms"],
        horizontal=True,
        index=0 if not st.session_state.get("comparison_mode") else 1
    )
    
    st.session_state["comparison_mode"] = (mode == "Compare All Platforms")
    
    product = st.text_input("Search Products")
    st.session_state[SESSION_PRODUCT_KEY] = product
    
    no_of_products = st.number_input(
        "No of products to search per platform",
        step=1,
        min_value=1,
        value=1
    )
    
    if mode == "Compare All Platforms":
        # Comparison mode
        if st.button("Compare Across All Platforms"):
            if not product:
                st.error("Please enter a product name to search")
                return
            
            try:
                comparison_service = ComparisonService(
                    product_name=product,
                    no_of_products=int(no_of_products)
                )
                
                with st.spinner("Scraping from all platforms in parallel..."):
                    platform_data = comparison_service.scrape_all_platforms()
                
                if not platform_data:
                    st.warning("No data found from any platform. Please try again.")
                    return
                
                # Store reviews in MongoDB
                mongoio = MongoIO()
                for platform, reviews_df in platform_data.items():
                    mongoio.store_reviews(
                        product_name=product,
                        reviews=reviews_df,
                        platform=platform
                    )
                
                # Generate comparison
                comparison_df = comparison_service.generate_comparison(platform_data)
                all_reviews_df = comparison_service.combine_all_reviews(platform_data)
                summary = comparison_service.get_comparison_summary(comparison_df)
                
                st.session_state["data"] = True
                
                # Display results
                display_comparison_results(comparison_df, all_reviews_df, summary)
                
                st.success(f"✅ Scraped and compared data from {len(platform_data)} platform(s)")
                
            except Exception as e:
                st.error(f"Error during comparison: {str(e)}")
                st.exception(e)
    else:
        # Single platform mode (original functionality)
        platform_display_map = {
            "Myntra": "myntra",
            "Flipkart": "flipkart",
            "Amazon": "amazon"
        }
        
        selected_platform_display = st.selectbox(
            "Select Platform",
            options=["Myntra", "Flipkart", "Amazon"],
            index=0
        )
        
        selected_platform = platform_display_map[selected_platform_display]
        st.session_state[SESSION_PLATFORM_KEY] = selected_platform

        if st.button("Scrape Reviews"):
            if not product:
                st.error("Please enter a product name to search")
                return
            
            try:
                # Dynamically import and instantiate the correct scraper
                if selected_platform == "myntra":
                    from src.scrapper.scrape import ScrapeReviews
                    scraper = ScrapeReviews(
                        product_name=product,
                        no_of_products=int(no_of_products)
                    )
                elif selected_platform == "flipkart":
                    from src.scrapper.flipkart_scraper import FlipkartScraper
                    scraper = FlipkartScraper(
                        product_name=product,
                        no_of_products=int(no_of_products)
                    )
                elif selected_platform == "amazon":
                    from src.scrapper.amazon_scraper import AmazonScraper
                    scraper = AmazonScraper(
                        product_name=product,
                        no_of_products=int(no_of_products)
                    )
                else:
                    st.error(f"Unknown platform: {selected_platform}")
                    return
                
                with st.spinner(f"Scraping reviews from {selected_platform_display}..."):
                    scrapped_data = scraper.get_review_data()
                
                if scrapped_data is not None and not scrapped_data.empty:
                    st.session_state["data"] = True
                    mongoio = MongoIO()
                    mongoio.store_reviews(
                        product_name=product,
                        reviews=scrapped_data,
                        platform=selected_platform
                    )
                    st.success(f"Stored {len(scrapped_data)} reviews into MongoDB")
                    st.dataframe(scrapped_data)
                else:
                    st.warning("No reviews found or scraping failed. Please try again.")
                    
            except Exception as e:
                st.error(f"Error during scraping: {str(e)}")
                st.exception(e)


if __name__ == "__main__":
    data = form_input()
