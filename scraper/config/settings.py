"""
Configuration settings for Instagram scraper.
Handles all configurable parameters with environment variable support.
"""

import os
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ScraperConfig:
    """Central configuration class for the Instagram scraper."""

    # Version
    SCRAPER_VERSION = "1.0.0"

    # Instagram Base URLs
    BASE_URL = "https://www.instagram.com"
    GRAPHQL_URL = f"{BASE_URL}/graphql/query/"

    # Request Configuration
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))  # seconds
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
    RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "2.0"))

    # Rate Limiting
    MIN_DELAY_BETWEEN_REQUESTS = float(os.getenv("MIN_DELAY", "2.0"))  # seconds
    MAX_DELAY_BETWEEN_REQUESTS = float(os.getenv("MAX_DELAY", "5.0"))  # seconds

    # Pagination Settings
    POSTS_PER_PAGE = int(os.getenv("POSTS_PER_PAGE", "50"))
    MAX_POSTS_TO_SCRAPE = int(os.getenv("MAX_POSTS_TO_SCRAPE", "0"))  # 0 = unlimited

    # Proxy Settings
    USE_PROXIES = os.getenv("USE_PROXIES", "false").lower() == "true"
    PROXY_LIST = os.getenv("PROXY_LIST", "").split(",") if os.getenv("PROXY_LIST") else []
    PROXY_ROTATION_ENABLED = os.getenv("PROXY_ROTATION", "true").lower() == "true"

    # User-Agent Settings
    ROTATE_USER_AGENTS = os.getenv("ROTATE_USER_AGENTS", "true").lower() == "true"
    CUSTOM_USER_AGENT = os.getenv("CUSTOM_USER_AGENT", None)

    # Output Settings
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")
    SAVE_RAW_HTML = os.getenv("SAVE_RAW_HTML", "false").lower() == "true"
    PRETTY_PRINT_JSON = os.getenv("PRETTY_PRINT_JSON", "true").lower() == "true"

    # Logging Settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", None)

    # Security Settings
    VERIFY_SSL = os.getenv("VERIFY_SSL", "true").lower() == "true"

    # Instagram Session Cookies (for authenticated requests)
    INSTAGRAM_SESSION_ID = os.getenv("INSTAGRAM_SESSION_ID", None)
    INSTAGRAM_CSRF_TOKEN = os.getenv("INSTAGRAM_CSRF_TOKEN", None)
    INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID", None)

    # Headers Configuration
    DEFAULT_HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    }

    # GraphQL Configuration
    # These may need to be updated periodically as Instagram changes them
    QUERY_HASH_USER_INFO = "58b6785bea111c67129decbe6a448951"
    QUERY_HASH_USER_POSTS = "69cba40317214236af40e7efa697781d"

    @classmethod
    def get_proxy(cls, index: int = 0) -> Optional[dict]:
        """
        Get proxy configuration by index.

        Args:
            index: Index in the proxy list

        Returns:
            Proxy dict or None if proxies disabled
        """
        if not cls.USE_PROXIES or not cls.PROXY_LIST:
            return None

        proxy_url = cls.PROXY_LIST[index % len(cls.PROXY_LIST)]
        return {
            "http": proxy_url,
            "https": proxy_url
        }

    @classmethod
    def validate_config(cls) -> bool:
        """
        Validate configuration settings.

        Returns:
            True if configuration is valid

        Raises:
            ValueError: If configuration is invalid
        """
        if cls.MIN_DELAY_BETWEEN_REQUESTS < 0:
            raise ValueError("MIN_DELAY_BETWEEN_REQUESTS must be >= 0")

        if cls.MAX_DELAY_BETWEEN_REQUESTS < cls.MIN_DELAY_BETWEEN_REQUESTS:
            raise ValueError("MAX_DELAY must be >= MIN_DELAY")

        if cls.MAX_RETRIES < 0:
            raise ValueError("MAX_RETRIES must be >= 0")

        if cls.REQUEST_TIMEOUT < 0:
            raise ValueError("REQUEST_TIMEOUT must be >= 0")

        if cls.USE_PROXIES and not cls.PROXY_LIST:
            raise ValueError("USE_PROXIES is true but PROXY_LIST is empty")

        return True


# Validate configuration on import
ScraperConfig.validate_config()
