import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import os, sys
from src.exception import CustomException
from src.utils.price_normalizer import normalize_prices_column


class DashboardGenerator:
    def __init__(self, data):
        self.data = data.copy()
        # Ensure Platform column exists
        if 'Platform' not in self.data.columns:
            self.data['Platform'] = 'Unknown'

    def display_general_info(self):
        st.header('General Information')

        # Convert 'Over_All_Rating' and 'Price' columns to numeric
        self.data['Over_All_Rating'] = pd.to_numeric(self.data['Over_All_Rating'], errors='coerce')

        # Normalize price with shared parser (handles INR, ₹, commas, decimals consistently).
        if 'Price' in self.data.columns:
            self.data = normalize_prices_column(self.data, price_col='Price')

        self.data["Rating"] = pd.to_numeric(self.data['Rating'], errors='coerce')

        # Platform distribution if multiple platforms exist
        if 'Platform' in self.data.columns and self.data['Platform'].nunique() > 1:
            st.subheader('Platform Distribution')
            platform_counts = self.data['Platform'].value_counts()
            fig_platform = px.pie(
                values=platform_counts.values, 
                names=platform_counts.index,
                title='Reviews by Platform'
            )
            st.plotly_chart(fig_platform)

        # Summary pie chart of average ratings by product
        product_ratings = self.data.groupby('Product Name', as_index=False)['Over_All_Rating'].mean().dropna()

        if not product_ratings.empty:
            fig_pie = px.pie(product_ratings, values='Over_All_Rating', names='Product Name',
                             title='Average Ratings by Product')
            st.plotly_chart(fig_pie)

        # Bar chart comparing average prices of different products with different colors
        if 'Price_Numeric' in self.data.columns:
            avg_prices = self.data.groupby('Product Name', as_index=False)['Price_Numeric'].mean().dropna()
            if not avg_prices.empty:
                fig_bar = px.bar(avg_prices, x='Product Name', y='Price_Numeric', color='Product Name',
                                 title='Average Price Comparison Between Products',
                                 color_discrete_sequence=px.colors.qualitative.Bold)
                fig_bar.update_xaxes(title='Product Name')
                fig_bar.update_yaxes(title='Average Price')
                st.plotly_chart(fig_bar)
        
        # Cross-platform comparison if multiple platforms
        if 'Platform' in self.data.columns and self.data['Platform'].nunique() > 1:
            st.subheader('Cross-Platform Rating Comparison')
            platform_ratings = self.data.groupby(['Platform', 'Product Name'], as_index=False)['Rating'].mean().dropna()
            if not platform_ratings.empty:
                fig_platform_comp = px.bar(
                    platform_ratings, 
                    x='Product Name', 
                    y='Rating', 
                    color='Platform',
                    title='Average Rating by Platform and Product',
                    barmode='group'
                )
                fig_platform_comp.update_xaxes(title='Product Name')
                fig_platform_comp.update_yaxes(title='Average Rating')
                st.plotly_chart(fig_platform_comp)
        
        # Sentiment analysis visualization if available
        if 'Sentiment_Score' in self.data.columns:
            st.subheader('📊 Sentiment Analysis')
            
            # Sentiment distribution
            if 'Sentiment_Label' in self.data.columns:
                sentiment_counts = self.data['Sentiment_Label'].value_counts()
                if not sentiment_counts.empty:
                    fig_sentiment = px.pie(
                        values=sentiment_counts.values,
                        names=sentiment_counts.index,
                        title='Sentiment Distribution',
                        color_discrete_map={
                            'positive': '#2ecc71',
                            'negative': '#e74c3c',
                            'neutral': '#95a5a6'
                        }
                    )
                    st.plotly_chart(fig_sentiment)
            
            # Average sentiment score by product
            if 'Product Name' in self.data.columns:
                product_sentiment = self.data.groupby('Product Name', as_index=False)['Sentiment_Score'].mean().dropna()
                if not product_sentiment.empty:
                    fig_product_sentiment = px.bar(
                        product_sentiment,
                        x='Product Name',
                        y='Sentiment_Score',
                        color='Sentiment_Score',
                        title='Average Sentiment Score by Product',
                        labels={'Sentiment_Score': 'Sentiment Score (-1 to 1)', 'Product Name': 'Product'},
                        color_continuous_scale='RdYlGn',
                        range_color=[-1, 1]
                    )
                    fig_product_sentiment.update_xaxes(title='Product Name')
                    fig_product_sentiment.update_yaxes(title='Sentiment Score', range=[-1, 1])
                    st.plotly_chart(fig_product_sentiment)
            
            # Sentiment vs Rating correlation
            if 'Rating' in self.data.columns:
                self.data['Rating'] = pd.to_numeric(self.data['Rating'], errors='coerce')
                sentiment_rating = self.data[['Sentiment_Score', 'Rating']].dropna()
                if not sentiment_rating.empty:
                    statsmodels_error = None
                    try:
                        import statsmodels.api  # noqa: F401
                        has_statsmodels = True
                    except Exception as exc:
                        has_statsmodels = False
                        statsmodels_error = str(exc)

                    scatter_kwargs = dict(
                        data_frame=sentiment_rating,
                        x='Rating',
                        y='Sentiment_Score',
                        title='Sentiment Score vs Rating Correlation',
                        labels={'Rating': 'Rating (1-5)', 'Sentiment_Score': 'Sentiment Score (-1 to 1)'},
                    )
                    if has_statsmodels:
                        try:
                            fig_corr = px.scatter(**scatter_kwargs, trendline='ols')
                        except Exception as exc:
                            fig_corr = px.scatter(**scatter_kwargs)
                            st.caption(f"Trendline disabled (`statsmodels`/`scipy` error: {exc}).")
                    else:
                        fig_corr = px.scatter(**scatter_kwargs)
                        if statsmodels_error:
                            st.caption(f"Trendline disabled (`statsmodels` unavailable: {statsmodels_error}).")
                        else:
                            st.caption("Trendline disabled (install `statsmodels` to enable OLS fit).")
                    fig_corr.update_xaxes(range=[0, 5])
                    fig_corr.update_yaxes(range=[-1, 1])
                    st.plotly_chart(fig_corr)

    def display_product_sections(self):
        st.header('Product Sections')

        product_names = self.data['Product Name'].unique()
        columns = st.columns(min(len(product_names), 3))  # Limit to 3 columns for better display

        for i, product_name in enumerate(product_names):
            product_data = self.data[self.data['Product Name'] == product_name]
            col_idx = i % len(columns)

            with columns[col_idx]:
                st.subheader(f'{product_name}')

                # Display platform if available
                if 'Platform' in product_data.columns:
                    platforms = product_data['Platform'].unique()
                    if len(platforms) > 0:
                        platform_str = ", ".join([p.capitalize() for p in platforms])
                        st.markdown(f"🏪 Platform(s): {platform_str}")

                # Display price in text or markdown with emojis
                if 'Price_Numeric' in product_data.columns:
                    avg_price = product_data['Price_Numeric'].mean()
                    if pd.notna(avg_price):
                        st.markdown(f"💰 Average Price: ₹{avg_price:.2f}")

                # Display average rating
                avg_rating = product_data['Over_All_Rating'].mean()
                if pd.notna(avg_rating):
                    st.markdown(f"⭐ Average Rating: {avg_rating:.2f}")

                # Display top positive comments with great ratings
                if 'Rating' in product_data.columns:
                    positive_reviews = product_data[product_data['Rating'] >= 4.5]
                    if not positive_reviews.empty:
                        positive_reviews = positive_reviews.nlargest(5, 'Rating')
                        st.subheader('Top Positive Reviews')
                        for index, row in positive_reviews.iterrows():
                            rating_display = f"{row['Rating']}" if pd.notna(row['Rating']) else "N/A"
                            comment = str(row['Comment'])[:200] + "..." if len(str(row['Comment'])) > 200 else str(row['Comment'])
                            st.markdown(f"✨ **{rating_display}⭐** - {comment}")

                    # Display top negative comments with worst ratings
                    negative_reviews = product_data[product_data['Rating'] <= 2]
                    if not negative_reviews.empty:
                        negative_reviews = negative_reviews.nsmallest(5, 'Rating')
                        st.subheader('Top Negative Reviews')
                        for index, row in negative_reviews.iterrows():
                            rating_display = f"{row['Rating']}" if pd.notna(row['Rating']) else "N/A"
                            comment = str(row['Comment'])[:200] + "..." if len(str(row['Comment'])) > 200 else str(row['Comment'])
                            st.markdown(f"💢 **{rating_display}⭐** - {comment}")

                    # Display rating counts in different categories
                    st.subheader('Rating Distribution')
                    rating_counts = product_data['Rating'].value_counts().sort_index(ascending=False)
                    if not rating_counts.empty:
                        fig_rating = px.bar(
                            x=rating_counts.index.astype(str),
                            y=rating_counts.values,
                            title='Rating Counts',
                            labels={'x': 'Rating', 'y': 'Count'}
                        )
                        st.plotly_chart(fig_rating, use_container_width=True)
                
                # Display sentiment information if available
                if 'Sentiment_Score' in product_data.columns:
                    avg_sentiment = product_data['Sentiment_Score'].mean()
                    if pd.notna(avg_sentiment):
                        sentiment_label = product_data['Sentiment_Label'].mode().iloc[0] if 'Sentiment_Label' in product_data.columns and not product_data['Sentiment_Label'].mode().empty else "N/A"
                        sentiment_emoji = "😊" if sentiment_label == "positive" else "😞" if sentiment_label == "negative" else "😐"
                        st.markdown(f"{sentiment_emoji} **Average Sentiment**: {avg_sentiment:.2f} ({sentiment_label})")
