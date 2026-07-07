"""
Sentiment analysis utilities using VADER sentiment analyzer.
VADER is optimized for social media text and handles emojis, slang, and informal language well.
"""

import logging
from typing import Dict, Optional
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)

# Initialize VADER analyzer (thread-safe, can be reused)
_analyzer = None


def get_analyzer() -> SentimentIntensityAnalyzer:
    """Get or create the VADER sentiment analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentIntensityAnalyzer()
        logger.debug("Initialized VADER sentiment analyzer")
    return _analyzer


def analyze_sentiment(text: str) -> Dict[str, float]:
    """
    Analyze sentiment of a text string.
    
    Args:
        text: Text to analyze (review comment)
        
    Returns:
        Dictionary with sentiment scores:
        - 'compound': Overall sentiment score (-1 to 1)
        - 'pos': Positive sentiment score (0 to 1)
        - 'neu': Neutral sentiment score (0 to 1)
        - 'neg': Negative sentiment score (0 to 1)
    """
    if not text or text.strip() == "" or text in ("No comment Given", "N/A", "None"):
        return {
            'compound': 0.0,
            'pos': 0.0,
            'neu': 1.0,
            'neg': 0.0
        }
    
    try:
        analyzer = get_analyzer()
        scores = analyzer.polarity_scores(text)
        return scores
    except Exception as e:
        logger.warning(f"Sentiment analysis failed for text: {str(e)[:100]}")
        return {
            'compound': 0.0,
            'pos': 0.0,
            'neu': 1.0,
            'neg': 0.0
        }


def get_sentiment_label(compound_score: float) -> str:
    """
    Convert compound sentiment score to label.
    
    Args:
        compound_score: Compound sentiment score from VADER (-1 to 1)
        
    Returns:
        Sentiment label: "positive", "negative", or "neutral"
    """
    if compound_score >= 0.05:
        return "positive"
    elif compound_score <= -0.05:
        return "negative"
    else:
        return "neutral"


def analyze_review_comment(comment: str) -> Dict[str, any]:
    """
    Analyze a review comment and return comprehensive sentiment information.
    
    Args:
        comment: Review comment text
        
    Returns:
        Dictionary with:
        - 'sentiment_score': Compound score (-1 to 1)
        - 'sentiment_label': "positive", "negative", or "neutral"
        - 'subjectivity': Subjectivity score (0 to 1, approximated from pos+neg scores)
    """
    scores = analyze_sentiment(comment)
    compound = scores['compound']
    
    # Subjectivity: higher when pos+neg is high (less neutral)
    # VADER doesn't provide subjectivity directly, so we approximate it
    subjectivity = scores['pos'] + scores['neg']
    
    return {
        'sentiment_score': compound,
        'sentiment_label': get_sentiment_label(compound),
        'subjectivity': subjectivity
    }

