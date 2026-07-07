import pandas as pd
import streamlit as st 
from src.cloud_io import MongoIO
from src.constants import SESSION_PRODUCT_KEY, SESSION_PLATFORM_KEY, SUPPORTED_PLATFORMS
from src.utils import fetch_product_names_from_cloud
from src.data_report.generate_data_report import DashboardGenerator
from src.utils.review_summarizer import summarize_by_product, summarize_all_reviews

# Lazy initialization - connection happens only when used
mongo_con = MongoIO()


def create_analysis_page(review_data: pd.DataFrame, product_name: str, platform: str = None):
    if review_data is not None and not review_data.empty:
        st.dataframe(review_data)
        
        # Summary section
        st.header("📝 Review Summary")
        
        # Check for cached summary
        cached_summary = mongo_con.get_summary(product_name=product_name, platform=platform)
        
        if cached_summary:
            st.info("📌 Using cached summary")
            st.write(cached_summary)
            if st.button("🔄 Regenerate Summary"):
                with st.spinner("Generating new summary... This may take a few seconds."):
                    if "Product Name" in review_data.columns and review_data["Product Name"].nunique() > 1:
                        summaries = summarize_by_product(review_data)
                        # Store first summary (or combine)
                        summary_text = "\n\n".join([f"**{prod}**: {summ}" for prod, summ in summaries.items()])
                    else:
                        summary_text = summarize_all_reviews(review_data)
                    
                    mongo_con.store_summary(product_name=product_name, summary=summary_text, platform=platform)
                    st.success("Summary generated and cached!")
                    st.rerun()
        else:
            if st.button("✨ Generate Summary"):
                with st.spinner("Generating summary... This may take a few seconds (first time will download model)."):
                    try:
                        if "Product Name" in review_data.columns and review_data["Product Name"].nunique() > 1:
                            summaries = summarize_by_product(review_data)
                            summary_text = "\n\n".join([f"**{prod}**: {summ}" for prod, summ in summaries.items()])
                        else:
                            summary_text = summarize_all_reviews(review_data)
                        
                        mongo_con.store_summary(product_name=product_name, summary=summary_text, platform=platform)
                        st.success("Summary generated and cached!")
                        st.write(summary_text)
                    except Exception as e:
                        st.error(f"Error generating summary: {str(e)}")
                        st.info("Make sure transformers and torch are installed: pip install transformers torch")
        
        if st.button("Generate Analysis"):
            dashboard = DashboardGenerator(review_data)
            
            # Display general information
            dashboard.display_general_info()
            
            # Display product-specific sections
            dashboard.display_product_sections()
    else:
        st.warning("No review data available for analysis.")


try:
    if st.session_state.get("data", False):
        product_name = st.session_state.get(SESSION_PRODUCT_KEY)
        
        if not product_name:
            st.warning("No product name found in session. Please go to the main page and scrape reviews first.")
        else:
            # Platform filter in sidebar
            with st.sidebar:
                st.header("Filter Options")
                
                # Platform selection
                platform_options = ["All Platforms"] + [p.capitalize() for p in SUPPORTED_PLATFORMS]
                selected_platform_display = st.selectbox(
                    "Select Platform",
                    options=platform_options,
                    index=0
                )
                
                if selected_platform_display == "All Platforms":
                    selected_platform = None
                    platform_display = "All Platforms"
                else:
                    selected_platform = selected_platform_display.lower()
                    platform_display = selected_platform_display
            
            # Get reviews based on platform selection
            try:
                data = mongo_con.get_reviews(
                    product_name=product_name,
                    platform=selected_platform
                )
            except Exception as e:
                st.error(f"Error loading reviews: {str(e)}")
                data = None
            
            if data is not None and not data.empty:
                st.header(f"Analysis for: {product_name}")
                if selected_platform:
                    st.subheader(f"Platform: {platform_display}")
                else:
                    st.subheader(f"Platform: {platform_display}")
                    # Show platform distribution if multiple platforms
                    if "Platform" in data.columns:
                        platform_counts = data["Platform"].value_counts()
                        st.write("**Reviews by Platform:**")
                        for platform, count in platform_counts.items():
                            st.write(f"- {platform.capitalize()}: {count} reviews")
                
                create_analysis_page(data, product_name=product_name, platform=selected_platform)
            else:
                st.warning(f"No reviews found for '{product_name}'" + 
                          (f" on {platform_display}" if selected_platform else ""))
    else:
        with st.sidebar:
            st.markdown("""
            ## No Data Available
            Please go to the main page and scrape reviews first.
            """)
        st.info("No data available for analysis. Please scrape reviews from the main page.")

except AttributeError as e:
    st.error(f"Session error: {str(e)}")
    st.markdown("""# No Data Available for analysis.""")
except Exception as e:
    st.error(f"Error loading analysis: {str(e)}")
    st.exception(e)
