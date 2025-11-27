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
        Instagram embeds JSON data in various script tags.
        """
        try:
            # Method 1: Try new data-sjs script tags (2024+ Instagram structure)
            soup = BeautifulSoup(html, 'lxml')
            
            # Look for script tags with data-sjs attribute
            sjs_scripts = soup.find_all('script', attrs={'data-sjs': True})
            for script in sjs_scripts:
                if script.string:
                    try:
                        data = json.loads(script.string)
                        # Check if this contains user profile data
                        if self._contains_profile_data(data):
                            logger.debug("Found profile data in data-sjs script")
                            return data
                    except json.JSONDecodeError:
                        continue
            
            # Method 2: Old patterns with regex
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
                    logger.debug(f"Successfully extracted shared data using pattern")
                    return data

            logger.warning("Could not find shared data in HTML with any known pattern")
            
            # Method 3: Try to use the API endpoint instead
            logger.info("Attempting to use API endpoint fallback")
            return None

        except Exception as e:
            logger.error(f"Error extracting shared data: {e}")
            return None

    def _contains_profile_data(self, data: Dict[str, Any]) -> bool:
        """Check if data contains profile information"""
        data_str = json.dumps(data)
        # Look for profile-related keys
        profile_indicators = ['username', 'follower', 'biography', 'edge_followed_by']
        return any(indicator in data_str for indicator in profile_indicators)


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

    def _parse_api_profile_data(self, user_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse profile data from Instagram's public API response.

        Args:
            user_data: User data from API response

        Returns:
            Parsed profile data or None
        """
        try:
            # Extract required fields with safe access
            profile = {
                'id': user_data.get('id'),
                'username': user_data.get('username'),
                'full_name': user_data.get('full_name', ''),
                'biography': user_data.get('biography', ''),
                'follower_count': user_data.get('edge_followed_by', {}).get('count', 0),
                'following_count': user_data.get('edge_follow', {}).get('count', 0),
                'posts_count': user_data.get('edge_owner_to_timeline_media', {}).get('count', 0),
                'profile_pic_url': user_data.get('profile_pic_url', ''),
                'profile_pic_url_hd': user_data.get('profile_pic_url_hd', ''),
                'is_verified': user_data.get('is_verified', False),
                'is_business_account': user_data.get('is_business_account', False),
                'is_professional_account': user_data.get('is_professional_account', False),
                'is_private': user_data.get('is_private', False),
                'category': user_data.get('category_name') or user_data.get('category_enum'),
                'external_url': user_data.get('external_url'),
                'scraped_at': datetime.utcnow().isoformat() + 'Z',
                'scraper_version': self.config.SCRAPER_VERSION,
            }

            # Validate required fields
            if not profile['username']:
                logger.error("Username not found in profile data")
                return None

            logger.info(f"Successfully parsed profile data for @{profile['username']}")
            logger.debug(f"Profile has {profile['posts_count']} posts, {profile['follower_count']} followers")

            return profile

        except Exception as e:
            logger.error(f"Error parsing API profile data: {e}", exc_info=True)
            return None

    def scrape_profile(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Scrape profile data for a given username using Instagram's public API.

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
            # Use Instagram's public web API
            api_url = f"{self.config.API_BASE_URL}/users/web_profile_info/"
            params = {"username": username}

            # Fetch profile data from API
            response = self.client.get(api_url, params=params)

            if response.status_code == 404:
                logger.error(f"Profile not found: @{username}")
                return None

            if response.status_code != 200:
                logger.error(f"Failed to fetch profile: HTTP {response.status_code}")
                return None

            # Parse JSON response
            try:
                data = response.json()
                # Save response for debugging if configured
                if self.config.SAVE_RAW_HTML:
                    import os
                    os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
                    with open(f"{self.config.OUTPUT_DIR}/{username}_profile_api_response.json", 'w') as f:
                        json.dump(data, f, indent=2)
                    logger.debug(f"Saved API response to {self.config.OUTPUT_DIR}/{username}_profile_api_response.json")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.debug(f"Response content: {response.text[:500]}")
                return None

            # Extract user data from API response
            user_data = data.get("data", {}).get("user")

            if not user_data:
                logger.error("No user data found in API response")
                logger.debug(f"Response structure: {list(data.keys())}")
                return None

            # Check if posts data is included (for potential extraction)
            has_posts = 'edge_owner_to_timeline_media' in user_data
            logger.debug(f"Profile API includes posts data: {has_posts}")
            if has_posts:
                posts_count_in_response = len(user_data.get('edge_owner_to_timeline_media', {}).get('edges', []))
                logger.info(f"Profile API returned {posts_count_in_response} initial posts")

            # Parse profile data from API response
            profile_data = self._parse_api_profile_data(user_data)

            if not profile_data:
                logger.error("Failed to parse profile data")
                return None

            # Store the full user data for posts extraction
            profile_data['_user_data'] = user_data

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
