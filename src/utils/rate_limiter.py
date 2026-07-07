"""
Rate limiter implementation using token bucket algorithm.
Thread-safe rate limiting to prevent IP bans during scraping.
"""

import time
from collections import deque
from threading import Lock
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Thread-safe rate limiter using token bucket algorithm.
    
    Tracks call timestamps and blocks requests that exceed the rate limit.
    """
    
    def __init__(self, max_calls: int, period: float = 60.0):
        """
        Initialize rate limiter.
        
        Args:
            max_calls: Maximum number of calls allowed in the period
            period: Time period in seconds (default: 60.0 for per-minute limiting)
        """
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()
        self.lock = Lock()
        logger.debug(f"Initialized rate limiter: {max_calls} calls per {period} seconds")
    
    def acquire(self) -> None:
        """
        Acquire permission to make a request.
        
        Blocks until the rate limit allows the request.
        Removes old timestamps outside the time window before checking.
        """
        with self.lock:
            now = time.time()
            
            # Remove timestamps outside the time window
            while self.calls and self.calls[0] <= now - self.period:
                self.calls.popleft()
            
            # If we've reached the limit, wait until the oldest call expires
            if len(self.calls) >= self.max_calls:
                oldest_call_time = self.calls[0]
                sleep_time = self.period - (now - oldest_call_time)
                
                if sleep_time > 0:
                    logger.debug(f"Rate limit reached. Sleeping for {sleep_time:.2f} seconds")
                    time.sleep(sleep_time)
                    # Remove the expired call after sleeping
                    self.calls.popleft()
            
            # Record this call
            self.calls.append(time.time())
            logger.debug(f"Rate limiter: {len(self.calls)}/{self.max_calls} calls in current window")
    
    def reset(self) -> None:
        """Reset the rate limiter (clear all call history)."""
        with self.lock:
            self.calls.clear()
            logger.debug("Rate limiter reset")
    
    def get_remaining_calls(self) -> int:
        """
        Get the number of remaining calls allowed in the current window.
        
        Returns:
            Number of calls remaining before hitting the limit
        """
        with self.lock:
            now = time.time()
            # Remove old timestamps
            while self.calls and self.calls[0] <= now - self.period:
                self.calls.popleft()
            return max(0, self.max_calls - len(self.calls))

