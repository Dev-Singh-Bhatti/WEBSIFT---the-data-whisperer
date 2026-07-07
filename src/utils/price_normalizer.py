"""Price normalization utility to convert various price formats to numeric values."""

import re
import pandas as pd


def normalize_price(price_str: str) -> float:
    """
    Normalize price string to numeric float.

    Handles formats like:
    - INR 285.00
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

    value = str(price_str).strip()
    if not value or value.upper() in {"N/A", "NA", "NONE", ""}:
        return pd.NA

    # Remove known currency markers but keep decimal points.
    value = value.replace("₹", "").replace("â‚¹", "")
    value = re.sub(r"(?i)\b(?:inr|rs|rupees?)\.?\b", "", value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", "", value)

    # Extract first numeric token (supports 1,23,456.78 and 123,456.78).
    match = re.search(r"(\d[\d,]*(?:\.\d+)?)", value)
    if not match:
        return pd.NA

    numeric_token = match.group(1).replace(",", "")
    try:
        return float(numeric_token)
    except ValueError:
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

