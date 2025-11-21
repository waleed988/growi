"""
Instagram Profile Scraper Module.
Extracts profile information from public Instagram accounts.
"""

import json
import re
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from bs4 import BeautifulSoup

from utils.http_client import HTTPClient
from config.settings import ScraperConfig

logger = logging.getLogger(__name__)


class ProfileScraper:
    """Scraper for Instagram profile data."""

    def __init__(self, http_client: HTTPClient):
        """
        Initialize profile scraper.

        Args:
            http_client: HTTP client instance
        """
        self.client = http_client
        self.config = ScraperConfig

    def _extract_shared_data(self, html: str) -> Optional[Dict[str, Any]]:
        """
        Extract shared data from HTML.
        Instagram embeds JSON data in window._sharedData or similar variables.

        Args:
            html: HTML content

        Returns:
            Extracted JSON data or None
        """
        try:
            # Try multiple patterns as Instagram changes the variable name
            patterns = [
                r'window\._sharedData\s*=\s*({.+?});</script>',
                r'window\.__additionalDataLoaded\([^,]+,\s*({.+?})\);</script>',
                r'<script type="text/javascript">window\._sharedData = ({.+?});</script>'
            ]

            for pattern in patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    data = json.loads(json_str)
                    logger.debug(f"Successfully extracted shared data using pattern: {pattern[:50]}")
                    return data

            logger.warning("Could not find shared data in HTML with any known pattern")
            return None

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse shared data JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Error extracting shared data: {e}")
            return None

    def _extract_graphql_data(self, html: str) -> Optional[Dict[str, Any]]:
        """
        Extract GraphQL data from script tags.
        Alternative method when _sharedData is not available.

        Args:
            html: HTML content

        Returns:
            Extracted GraphQL data or None
        """
        try:
            soup = BeautifulSoup(html, 'lxml')
            scripts = soup.find_all('script', type='application/ld+json')

            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if data and isinstance(data, dict):
                        logger.debug("Successfully extracted GraphQL data from ld+json")
                        return data
                except json.JSONDecodeError:
                    continue

            return None

        except Exception as e:
            logger.error(f"Error extracting GraphQL data: {e}")
            return None

    def _parse_profile_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse profile data from extracted JSON.

        Args:
            data: Extracted JSON data

        Returns:
            Parsed profile data or None
        """
        try:
            # Navigate the nested structure
            # Structure can vary: entry_data.ProfilePage[0].graphql.user
            profile_data = None

            # Try different paths
            if 'entry_data' in data:
                if 'ProfilePage' in data['entry_data']:
                    profile_page = data['entry_data']['ProfilePage'][0]
                    if 'graphql' in profile_page:
                        profile_data = profile_page['graphql']['user']
                    elif 'user' in profile_page:
                        profile_data = profile_page['user']

            # Alternative structure
            elif 'graphql' in data:
                if 'user' in data['graphql']:
                    profile_data = data['graphql']['user']

            # Direct user data
            elif 'user' in data:
                profile_data = data['user']

            if not profile_data:
                logger.error("Could not locate user data in JSON structure")
                return None

            # Extract required fields with safe access
            profile = {
                'username': profile_data.get('username'),
                'full_name': profile_data.get('full_name', ''),
                'biography': profile_data.get('biography', ''),
                'follower_count': profile_data.get('edge_followed_by', {}).get('count', 0),
                'following_count': profile_data.get('edge_follow', {}).get('count', 0),
                'posts_count': profile_data.get('edge_owner_to_timeline_media', {}).get('count', 0),
                'profile_pic_url': profile_data.get('profile_pic_url', ''),
                'profile_pic_url_hd': profile_data.get('profile_pic_url_hd', ''),
                'is_verified': profile_data.get('is_verified', False),
                'is_business_account': profile_data.get('is_business_account', False),
                'is_professional_account': profile_data.get('is_professional_account', False),
                'is_private': profile_data.get('is_private', False),
                'category': profile_data.get('category_name') or profile_data.get('category_enum'),
                'external_url': profile_data.get('external_url'),
                'scraped_at': datetime.utcnow().isoformat() + 'Z',
                'scraper_version': self.config.SCRAPER_VERSION,
            }

            # Validate required fields
            if not profile['username']:
                logger.error("Username not found in profile data")
                return None

            logger.info(f"Successfully parsed profile data for @{profile['username']}")
            return profile

        except Exception as e:
            logger.error(f"Error parsing profile data: {e}", exc_info=True)
            return None

    def scrape_profile(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Scrape profile data for a given username.

        Args:
            username: Instagram username (without @)

        Returns:
            Profile data dict or None on failure
        """
        # Sanitize username
        username = username.strip().lstrip('@').lower()

        if not username:
            logger.error("Invalid username provided")
            return None

        # Validate username format
        if not re.match(r'^[a-zA-Z0-9._]+$', username):
            logger.error(f"Invalid username format: {username}")
            return None

        logger.info(f"Starting profile scrape for @{username}")

        try:
            # Build profile URL
            profile_url = f"{self.config.BASE_URL}/{username}/"

            # Fetch profile page
            response = self.client.get(profile_url)

            if response.status_code == 404:
                logger.error(f"Profile not found: @{username}")
                return None

            if response.status_code != 200:
                logger.error(f"Failed to fetch profile: HTTP {response.status_code}")
                return None

            # Get HTML content (requests auto-decodes based on Content-Encoding header)
            html = response.text

            # Debug: Check if we got valid HTML
            if not html or len(html) < 1000:
                logger.error(f"Response too short or empty: {len(html)} bytes")
                logger.debug(f"Response headers: {dict(response.headers)}")
                logger.debug(f"First 200 chars: {html[:200]}")
                return None

            # Check if HTML looks valid (should start with <!DOCTYPE or <html)
            if not (html.strip().startswith('<!DOCTYPE') or html.strip().startswith('<html')):
                logger.warning(f"Response doesn't look like HTML. First 100 chars: {html[:100]}")
                logger.debug(f"Content-Type: {response.headers.get('content-type')}")
                logger.debug(f"Content-Encoding: {response.headers.get('content-encoding')}")

            # Save raw HTML if configured
            if self.config.SAVE_RAW_HTML:
                output_path = f"{self.config.OUTPUT_DIR}/{username}_profile.html"
                try:
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(html)
                    logger.debug(f"Saved raw HTML to {output_path}")
                except Exception as e:
                    logger.warning(f"Failed to save raw HTML: {e}")

            # Extract data
            shared_data = self._extract_shared_data(html)
            if not shared_data:
                logger.warning("Trying alternative extraction method...")
                shared_data = self._extract_graphql_data(html)

            if not shared_data:
                logger.error("Failed to extract any data from profile page")
                return None

            # Parse profile data
            profile_data = self._parse_profile_data(shared_data)

            if not profile_data:
                logger.error("Failed to parse profile data")
                return None

            logger.info(f"Successfully scraped profile @{username}")
            return profile_data

        except Exception as e:
            logger.error(f"Error scraping profile @{username}: {e}", exc_info=True)
            return None

    def get_user_id(self, profile_data: Dict[str, Any], html: str = None) -> Optional[str]:
        """
        Extract user ID from profile data or HTML.
        Required for GraphQL queries.

        Args:
            profile_data: Profile data dict
            html: HTML content (optional)

        Returns:
            User ID string or None
        """
        try:
            # Try to extract from various locations
            if 'id' in profile_data:
                return str(profile_data['id'])

            # If HTML provided, try to extract from there
            if html:
                match = re.search(r'"owner":{"id":"(\d+)"', html)
                if match:
                    return match.group(1)

                match = re.search(r'"profilePage_(\d+)"', html)
                if match:
                    return match.group(1)

            logger.warning("Could not extract user ID")
            return None

        except Exception as e:
            logger.error(f"Error extracting user ID: {e}")
            return None
