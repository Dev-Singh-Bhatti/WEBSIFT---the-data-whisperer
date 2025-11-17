import pandas as pd
import streamlit as st 
from src.cloud_io import MongoIO
from src.constants import SESSION_PRODUCT_KEY, SESSION_PLATFORM_KEY, SUPPORTED_PLATFORMS
from src.utils import fetch_product_names_from_cloud
from src.data_report.generate_data_report import DashboardGenerator
from pymongo.errors import ConfigurationError, ServerSelectionTimeoutError

# Lazy initialization - connection happens only when used
mongo_con = MongoIO()


def create_analysis_page(review_data: pd.DataFrame):
    if review_data is not None and not review_data.empty:
        st.dataframe(review_data)
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
            except (ConfigurationError, ServerSelectionTimeoutError) as e:
                st.error(f"MongoDB connection error: {str(e)}")
                st.warning("Cannot load reviews from database. Please check your MongoDB connection settings.")
                data = None
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
                
                create_analysis_page(data)
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

