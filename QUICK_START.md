# Quick Start Guide - Improved Scraping Codebase

## What's New? 🚀

Your scraping codebase has been enhanced with:

1. **Anti-Bot Detection Improvements**
   - ✅ User-Agent rotation (7 realistic agents)
   - ✅ WebGL fingerprint randomization
   - ✅ Enhanced stealth configuration
   - ✅ Human-like delay patterns
   - ✅ Proxy support infrastructure

2. **Stability Enhancements**
   - ✅ Robust retry logic with exponential backoff
   - ✅ Multi-selector fallback utilities
   - ✅ Better error handling and logging
   - ✅ Bot detection pattern checking

3. **Configuration Management**
   - ✅ Centralized config via `src/config.py`
   - ✅ Environment variable support
   - ✅ Example configuration file

## Usage

### Basic Usage (No Changes Required)

```python
from src.scrapper.amazon_scraper import AmazonScraper

# Works exactly as before - all improvements are automatic
scraper = AmazonScraper("laptop", 5)
data = scraper.get_review_data()
```

### With Proxy (Optional)

```python
# Option 1: Pass proxy directly
scraper = AmazonScraper("laptop", 5, proxy="http://proxy.example.com:8080")

# Option 2: Configure in src/config.py
# Set PROXY_ENABLED = True and PROXY_LIST = ["http://proxy1:port", ...]
```

### Configuration

Edit `src/config.py` or set environment variables:

```bash
# Example: Enable proxy rotation
export PROXY_ENABLED=true
export PROXY_LIST="http://proxy1:8080,http://proxy2:8080"

# Adjust delays
export MIN_DELAY=3
export MAX_DELAY=7
```

## Key Improvements

### 1. User-Agent Rotation
- Automatically rotates through 7 realistic user agents
- Matches platform (Windows/Mac/Linux) to user agent
- Updated for 2024 browser versions

### 2. Fingerprint Randomization
- Randomizes WebGL vendor/renderer
- Randomizes screen resolution
- Randomizes platform detection

### 3. Human-Like Behavior
- Variable scroll speeds with bezier curves
- Reading pauses (10% chance of longer delays)
- Beta distribution for delay patterns (favors shorter, occasional long)

### 4. Better Error Handling
- Retry with exponential backoff
- Multi-selector fallback
- Bot detection pattern checking
- Structured logging

## Files Changed

- ✅ `src/scrapper/base_scraper.py` - Enhanced stealth, user-agent rotation, proxy support
- ✅ `src/config.py` - Added comprehensive configuration options
- ✅ `src/utils/scraping_utils.py` - New utility functions
- ✅ `src/scrapper/amazon_scraper.py` - Updated to use new utilities
- ✅ `IMPROVEMENTS.md` - Comprehensive improvement documentation

## Testing

1. **Test Basic Functionality**
   ```python
   python -c "from src.scrapper.amazon_scraper import AmazonScraper; s = AmazonScraper('test', 1); print('OK')"
   ```

2. **Check Logs**
   - Logs are written to `logs/scraper_YYYY-MM-DD.log`
   - Console output shows INFO level and above

3. **Monitor for Bot Detection**
   - Check logs for "Bot detection pattern found" warnings
   - If detected, increase delays or use proxies

## Best Practices

1. **Start Conservative**: Use default delays (2-5 seconds)
2. **Monitor Logs**: Check for bot detection warnings
3. **Use Proxies**: For production, enable proxy rotation
4. **Respect Rate Limits**: Don't exceed 10 requests/minute
5. **Handle Failures**: Use retry logic for transient errors

## Troubleshooting

### "Bot detection detected"
- Increase `MIN_DELAY` and `MAX_DELAY` in config
- Enable proxy rotation
- Reduce `REQUESTS_PER_MINUTE`

### "Chrome driver initialization failed"
- Ensure ChromeDriver is installed and in PATH
- Check Chrome browser version matches ChromeDriver

### "No products found"
- Check if website structure changed
- Verify selectors in scraper code
- Check logs for specific errors

## Next Steps

1. Review `IMPROVEMENTS.md` for detailed analysis
2. Configure proxies if needed (see `config.example.py`)
3. Test with your use case
4. Monitor logs for issues
5. Adjust configuration as needed

## Support

- Check logs in `logs/` directory
- Review `IMPROVEMENTS.md` for detailed explanations
- See `src/utils/scraping_utils.py` for utility functions

---

**Status**: ✅ All improvements implemented and tested
**Backward Compatibility**: ✅ 100% - existing code works without changes

