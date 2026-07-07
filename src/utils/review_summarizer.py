"""
Review summarization using BART model via transformers.
Generates concise summaries of product reviews.
"""

import logging
from typing import List, Dict
import pandas as pd
from collections import Counter
import re

logger = logging.getLogger(__name__)

# Lazy loading of model to avoid import overhead
_summarizer = None
_summarizer_load_attempted = False

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for",
    "from", "had", "has", "have", "i", "if", "in", "is", "it", "its", "me",
    "my", "of", "on", "or", "our", "so", "that", "the", "their", "them",
    "there", "this", "to", "was", "we", "were", "with", "you", "your", "very",
    "product", "buy", "using", "use", "good", "great", "nice"
}


def _fallback_extractive_summary(reviews: List[str], max_points: int = 4) -> str:
    """
    Lightweight fallback summary when transformer model is unavailable.
    """
    if not reviews:
        return "No reviews available for summarization."

    cleaned = [re.sub(r"\s+", " ", str(r)).strip() for r in reviews if r and str(r).strip()]
    if not cleaned:
        return "No valid reviews available for summarization."

    # Top recurring keywords as coarse themes.
    tokens = []
    for review in cleaned:
        for token in re.findall(r"[A-Za-z]{3,}", review.lower()):
            if token not in _STOPWORDS:
                tokens.append(token)

    top_terms = [word for word, _ in Counter(tokens).most_common(6)]

    # Representative snippets: longest distinct reviews usually contain stronger signal.
    seen = set()
    snippets = []
    for review in sorted(cleaned, key=len, reverse=True):
        key = review.lower()
        if key in seen:
            continue
        seen.add(key)
        snippets.append(review[:220].rstrip(" ."))
        if len(snippets) >= max_points:
            break

    parts = [f"Summary based on {len(cleaned)} review(s)."]
    if top_terms:
        parts.append("Common themes: " + ", ".join(top_terms) + ".")
    if snippets:
        parts.append("Representative feedback: " + " | ".join(snippets) + ".")

    return " ".join(parts)


def get_summarizer():
    """Get or create the BART summarizer instance (lazy loading)."""
    global _summarizer, _summarizer_load_attempted
    if _summarizer is None:
        if _summarizer_load_attempted:
            return None
        _summarizer_load_attempted = True
        try:
            from transformers import pipeline
            logger.info("Loading BART summarization model (first time may take a while)...")
            _summarizer = pipeline(
                "summarization",
                model="facebook/bart-large-cnn",
                device=-1  # Use CPU (-1), set to 0 for GPU if available
            )
            logger.info("BART summarization model loaded successfully")
        except ImportError:
            logger.warning(
                "transformers library not installed. Falling back to extractive summary."
            )
            return None
        except Exception as e:
            logger.warning(f"Failed to load transformer summarizer. Using fallback. Error: {e}")
            return None
    return _summarizer


def summarize_reviews(reviews: List[str], max_length: int = 150, min_length: int = 50) -> str:
    """
    Summarize a list of review comments.
    
    Args:
        reviews: List of review comment strings
        max_length: Maximum length of summary in tokens
        min_length: Minimum length of summary in tokens
        
    Returns:
        Summary string
    """
    if not reviews:
        return "No reviews available for summarization."
    
    # Filter out empty or placeholder reviews
    valid_reviews = [
        r for r in reviews 
        if r and r.strip() and r not in ("No comment Given", "N/A", "None", "")
    ]
    
    if not valid_reviews:
        return "No valid reviews available for summarization."
    
    # Combine reviews into single text (limit to avoid token limits)
    # BART has a max input length of 1024 tokens, so we limit to ~50 reviews
    max_reviews = 50
    if len(valid_reviews) > max_reviews:
        logger.warning(f"Limiting summarization to first {max_reviews} reviews (out of {len(valid_reviews)})")
        valid_reviews = valid_reviews[:max_reviews]
    
    combined_text = " ".join(valid_reviews)
    
    # Truncate if too long (rough estimate: 4 chars per token, 1024 tokens = ~4000 chars)
    max_chars = 4000
    if len(combined_text) > max_chars:
        combined_text = combined_text[:max_chars]
        logger.warning(f"Truncated review text to {max_chars} characters for summarization")
    
    try:
        summarizer = get_summarizer()
        if summarizer is None:
            return _fallback_extractive_summary(valid_reviews)

        result = summarizer(
            combined_text,
            max_length=max_length,
            min_length=min_length,
            do_sample=False  # Deterministic output
        )
        
        if isinstance(result, list) and len(result) > 0:
            summary = result[0].get('summary_text', '')
            return summary
        else:
            logger.warning("Summarizer returned unexpected format")
            return _fallback_extractive_summary(valid_reviews)
            
    except Exception as e:
        logger.error(f"Error during summarization: {e}")
        return _fallback_extractive_summary(valid_reviews)


def summarize_by_product(df: pd.DataFrame, comment_col: str = "Comment") -> Dict[str, str]:
    """
    Generate summaries for each product in a DataFrame.
    
    Args:
        df: DataFrame with reviews
        comment_col: Name of the column containing review comments
        
    Returns:
        Dictionary mapping product names to summaries
    """
    if df.empty or comment_col not in df.columns:
        return {}
    
    summaries = {}
    product_col = "Product Name" if "Product Name" in df.columns else None
    
    if product_col:
        # Group by product
        for product_name, product_df in df.groupby(product_col):
            comments = product_df[comment_col].dropna().tolist()
            if comments:
                logger.info(f"Generating summary for product: {product_name}")
                summary = summarize_reviews(comments)
                summaries[product_name] = summary
    else:
        # No product grouping, summarize all reviews together
        comments = df[comment_col].dropna().tolist()
        if comments:
            summary = summarize_reviews(comments)
            summaries["All Products"] = summary
    
    return summaries


def summarize_all_reviews(df: pd.DataFrame, comment_col: str = "Comment") -> str:
    """
    Generate a single summary for all reviews in the DataFrame.
    
    Args:
        df: DataFrame with reviews
        comment_col: Name of the column containing review comments
        
    Returns:
        Summary string
    """
    if df.empty or comment_col not in df.columns:
        return "No reviews available for summarization."
    
    comments = df[comment_col].dropna().tolist()
    return summarize_reviews(comments)

