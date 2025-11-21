"""
HTTP Client with retry logic, rate limiting, and anti-blocking measures.
"""

import time
import random
import logging
from typing import Optional, Dict, Any
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from fake_useragent import UserAgent
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from config.settings import ScraperConfig

logger = logging.getLogger(__name__)


class RateLimitException(Exception):
    """Raised when rate limit is detected."""
    pass


class BannedException(Exception):
    """Raised when IP/session is banned."""
    pass


class HTTPClient:
    """
    HTTP client with advanced features for web scraping:
    - Retry logic with exponential backoff
    - Rate limiting
    - Proxy rotation
    - User-agent rotation
    - Session management
    """

    def __init__(self):
        """Initialize HTTP client with session and configuration."""
        self.session = requests.Session()
        self.config = ScraperConfig
        self.user_agent_rotator = UserAgent() if self.config.ROTATE_USER_AGENTS else None
        self.proxy_index = 0
        self.request_count = 0

        # Configure session with retry strategy
        retry_strategy = Retry(
            total=self.config.MAX_RETRIES,
            backoff_factor=self.config.RETRY_BACKOFF_FACTOR,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            raise_on_status=False
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set default headers
        self._update_headers()

        # Set Instagram session cookies if provided
        self._set_instagram_cookies()

        logger.info("HTTP Client initialized successfully")

    def _update_headers(self) -> None:
        """Update session headers with user-agent rotation."""
        headers = self.config.DEFAULT_HEADERS.copy()

        # Set user agent
        if self.config.CUSTOM_USER_AGENT:
            headers["User-Agent"] = self.config.CUSTOM_USER_AGENT
        elif self.user_agent_rotator:
            try:
                headers["User-Agent"] = self.user_agent_rotator.random
            except Exception as e:
                logger.warning(f"Failed to get random user agent: {e}, using fallback")
                headers["User-Agent"] = (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
        else:
            headers["User-Agent"] = (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )

        self.session.headers.update(headers)
        logger.debug(f"Headers updated with User-Agent: {headers['User-Agent'][:50]}...")

    def _set_instagram_cookies(self) -> None:
        """Set Instagram session cookies if provided in configuration."""
        if self.config.INSTAGRAM_SESSION_ID:
            cookies = {
                'sessionid': self.config.INSTAGRAM_SESSION_ID,
            }

            if self.config.INSTAGRAM_CSRF_TOKEN:
                cookies['csrftoken'] = self.config.INSTAGRAM_CSRF_TOKEN

            if self.config.INSTAGRAM_USER_ID:
                cookies['ds_user_id'] = self.config.INSTAGRAM_USER_ID

            # Set cookies for Instagram domain
            for name, value in cookies.items():
                self.session.cookies.set(
                    name=name,
                    value=value,
                    domain='.instagram.com',
                    path='/'
                )

            logger.info(f"Instagram session cookies configured ({len(cookies)} cookies)")
            logger.debug(f"Cookie names: {list(cookies.keys())}")
        else:
            logger.debug("No Instagram session cookies configured (scraping public data)")

    def _get_next_proxy(self) -> Optional[Dict[str, str]]:
        """
        Get next proxy from the rotation pool.

        Returns:
            Proxy configuration dict or None
        """
        if not self.config.USE_PROXIES or not self.config.PROXY_LIST:
            return None

        if self.config.PROXY_ROTATION_ENABLED:
            proxy = self.config.get_proxy(self.proxy_index)
            self.proxy_index = (self.proxy_index + 1) % len(self.config.PROXY_LIST)
            logger.debug(f"Using proxy index {self.proxy_index}")
            return proxy

        return self.config.get_proxy(0)

    def _rate_limit(self) -> None:
        """
        Implement rate limiting between requests.
        Random delay between MIN_DELAY and MAX_DELAY seconds.
        """
        delay = random.uniform(
            self.config.MIN_DELAY_BETWEEN_REQUESTS,
            self.config.MAX_DELAY_BETWEEN_REQUESTS
        )
        logger.debug(f"Rate limiting: sleeping for {delay:.2f} seconds")
        time.sleep(delay)

    def _check_response_for_ban(self, response: requests.Response) -> None:
        """
        Check if response indicates a ban or rate limit.

        Args:
            response: Response object to check

        Raises:
            RateLimitException: If rate limited
            BannedException: If banned
        """
        # Check for rate limit
        if response.status_code == 429:
            logger.warning("Rate limit detected (HTTP 429)")
            raise RateLimitException("Rate limit exceeded")

        # Check for redirect to login (indicates ban)
        if response.status_code == 302 and "/accounts/login/" in response.headers.get("Location", ""):
            logger.error("Redirect to login detected - possible ban")
            raise BannedException("Session banned - redirect to login")

        # Check for challenge page
        if "challenge" in response.url.lower():
            logger.error("Challenge page detected - account verification required")
            raise BannedException("Challenge page detected")

        # Check for empty/suspicious responses
        if response.status_code == 200 and len(response.content) < 1000:
            logger.warning("Suspiciously small response - possible soft ban")
            # Don't raise exception, but log for monitoring

    def _handle_retry_on_ban(self, retry_state) -> None:
        """
        Handle retry logic when ban is detected.

        Args:
            retry_state: Retry state from tenacity
        """
        logger.warning(f"Retry attempt {retry_state.attempt_number} after ban detection")

        # Rotate proxy if available
        if self.config.USE_PROXIES:
            logger.info("Rotating proxy...")
            self._get_next_proxy()

        # Rotate user agent
        if self.config.ROTATE_USER_AGENTS:
            logger.info("Rotating user agent...")
            self._update_headers()

        # Longer backoff on ban
        sleep_time = min(60, 2 ** retry_state.attempt_number)
        logger.info(f"Sleeping for {sleep_time} seconds before retry...")
        time.sleep(sleep_time)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((RateLimitException, requests.ConnectionError, requests.Timeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        use_rate_limit: bool = True
    ) -> requests.Response:
        """
        Perform GET request with retry logic and rate limiting.

        Args:
            url: URL to fetch
            params: Query parameters
            headers: Additional headers
            use_rate_limit: Whether to apply rate limiting

        Returns:
            Response object

        Raises:
            RateLimitException: If rate limited
            BannedException: If banned
            requests.RequestException: On request failure
        """
        # Apply rate limiting
        if use_rate_limit and self.request_count > 0:
            self._rate_limit()

        # Merge additional headers
        request_headers = self.session.headers.copy()
        if headers:
            request_headers.update(headers)

        # Get proxy
        proxies = self._get_next_proxy()

        try:
            logger.info(f"GET request to: {url}")
            response = self.session.get(
                url,
                params=params,
                headers=request_headers,
                proxies=proxies,
                timeout=self.config.REQUEST_TIMEOUT,
                verify=self.config.VERIFY_SSL,
                allow_redirects=True
            )

            # Check for bans
            self._check_response_for_ban(response)

            # Raise for bad status codes (except those handled by retry)
            if response.status_code >= 400 and response.status_code not in [429, 500, 502, 503, 504]:
                logger.error(f"HTTP {response.status_code} error for {url}")
                response.raise_for_status()

            self.request_count += 1
            logger.info(f"Request successful: {response.status_code} (Total requests: {self.request_count})")

            return response

        except (RateLimitException, BannedException):
            # Re-raise these for retry logic
            raise
        except requests.Timeout as e:
            logger.error(f"Request timeout for {url}: {e}")
            raise
        except requests.ConnectionError as e:
            logger.error(f"Connection error for {url}: {e}")
            raise
        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            raise

    def post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> requests.Response:
        """
        Perform POST request (for GraphQL queries).

        Args:
            url: URL to post to
            data: Form data
            json: JSON data
            headers: Additional headers

        Returns:
            Response object

        Raises:
            requests.RequestException: On request failure
        """
        # Apply rate limiting
        if self.request_count > 0:
            self._rate_limit()

        # Merge headers
        request_headers = self.session.headers.copy()
        if headers:
            request_headers.update(headers)

        # Get proxy
        proxies = self._get_next_proxy()

        try:
            logger.info(f"POST request to: {url}")
            response = self.session.post(
                url,
                data=data,
                json=json,
                headers=request_headers,
                proxies=proxies,
                timeout=self.config.REQUEST_TIMEOUT,
                verify=self.config.VERIFY_SSL
            )

            self._check_response_for_ban(response)
            response.raise_for_status()

            self.request_count += 1
            logger.info(f"POST request successful: {response.status_code}")

            return response

        except requests.RequestException as e:
            logger.error(f"POST request failed for {url}: {e}")
            raise

    def close(self) -> None:
        """Close the session and cleanup resources."""
        self.session.close()
        logger.info("HTTP Client session closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
