"""Price normalization utility to convert various price formats to numeric values."""

import re
import pandas as pd


def normalize_price(price_str: str) -> float:
    """
    Normalize price string to numeric float.
    
    Handles formats like:
    - ₹1,234.56
    - Rs. 1234
    - 1,234 INR
    - N/A, None, empty
    
    Args:
        price_str: Price string in various formats
        
    Returns:
        Float value or NaN if unparseable
    """
    if pd.isna(price_str) or price_str is None:
        return pd.NA
    
    price_str = str(price_str).strip()
    
    if not price_str or price_str.upper() in ("N/A", "NA", "NONE", ""):
        return pd.NA
    
    # Remove currency symbols and common prefixes
    price_str = re.sub(r'[₹Rs\.rs\.INR\s]', '', price_str, flags=re.IGNORECASE)
    
    # Remove commas
    price_str = price_str.replace(',', '')
    
    # Extract first number (handles cases like "1234.56 INR" or "Price: 1234")
    match = re.search(r'(\d+\.?\d*)', price_str)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return pd.NA
    
    return pd.NA


def normalize_prices_column(df: pd.DataFrame, price_col: str = "Price") -> pd.DataFrame:
    """
    Normalize price column in DataFrame.
    
    Args:
        df: DataFrame with price column
        price_col: Name of price column (default: "Price")
        
    Returns:
        DataFrame with normalized numeric prices in new column "Price_Numeric"
    """
    df = df.copy()
    if price_col in df.columns:
        df["Price_Numeric"] = df[price_col].apply(normalize_price)
    else:
        df["Price_Numeric"] = pd.NA
    return df

