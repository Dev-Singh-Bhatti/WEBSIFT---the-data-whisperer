"""
Quick test script to verify Amazon scraper imports and basic structure.
Run this to check if the scraper is properly configured.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test if all imports work correctly."""
    try:
        from src.scrapper.amazon_scraper import AmazonScraper
        from src.scrapper.base_scraper import BaseScraper
        from src.utils.scraping_utils import (
            check_bot_detection,
            extract_text_safe,
            normalize_rating,
            human_like_delay
        )
        from src.config import PROXY_ENABLED, PROXY_LIST
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_class_structure():
    """Test if AmazonScraper has required methods."""
    try:
        from src.scrapper.amazon_scraper import AmazonScraper
        
        # Check required methods exist
        required_methods = [
            'scrape_product_urls',
            'extract_reviews',
            'extract_products',
            'get_review_data'
        ]
        
        for method in required_methods:
            if not hasattr(AmazonScraper, method):
                print(f"❌ Missing method: {method}")
                return False
        
        print("✅ All required methods exist")
        return True
    except Exception as e:
        print(f"❌ Structure check error: {e}")
        return False

def test_config():
    """Test if configuration is accessible."""
    try:
        from src.config import (
            PROXY_ENABLED,
            PROXY_LIST,
            MIN_DELAY,
            MAX_DELAY,
            MAX_RETRIES
        )
        print(f"✅ Configuration loaded:")
        print(f"   - PROXY_ENABLED: {PROXY_ENABLED}")
        print(f"   - MIN_DELAY: {MIN_DELAY}")
        print(f"   - MAX_DELAY: {MAX_DELAY}")
        print(f"   - MAX_RETRIES: {MAX_RETRIES}")
        return True
    except Exception as e:
        print(f"❌ Config error: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 50)
    print("Amazon Scraper Verification Test")
    print("=" * 50)
    print()
    
    results = []
    
    print("1. Testing imports...")
    results.append(test_imports())
    print()
    
    print("2. Testing class structure...")
    results.append(test_class_structure())
    print()
    
    print("3. Testing configuration...")
    results.append(test_config())
    print()
    
    print("=" * 50)
    if all(results):
        print("✅ All tests passed! Amazon scraper is ready to use.")
        print()
        print("Note: This test only verifies code structure.")
        print("To test actual scraping, you need:")
        print("  - ChromeDriver installed")
        print("  - Selenium installed")
        print("  - Internet connection")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

