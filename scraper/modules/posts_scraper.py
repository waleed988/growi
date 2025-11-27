"""
Instagram Posts Scraper Module with Pagination Support.
Extracts posts from public Instagram accounts.
"""

import json
import re
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from utils.http_client import HTTPClient
from config.settings import ScraperConfig

logger = logging.getLogger(__name__)


class PostsScraper:
    """Scraper for Instagram posts with full pagination support."""

    def __init__(self, http_client: HTTPClient):
        """
        Initialize posts scraper.

        Args:
            http_client: HTTP client instance
        """
        self.client = http_client
        self.config = ScraperConfig

    def _extract_initial_posts(self, html: str) -> tuple[List[Dict[str, Any]], Optional[str], Optional[str]]:
        """
        Extract initial posts from profile HTML page.

        Args:
            html: HTML content from profile page

        Returns:
            Tuple of (posts_list, end_cursor, user_id)
        """
        try:
            # Extract shared data
            patterns = [
                r'window\._sharedData\s*=\s*({.+?});</script>',
                r'window\.__additionalDataLoaded\([^,]+,\s*({.+?})\);</script>',
            ]

            shared_data = None
            for pattern in patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    shared_data = json.loads(match.group(1))
                    break

            if not shared_data:
                logger.error("Could not extract shared data for posts")
                return [], None, None

            # Navigate to posts data
            posts_data = None
            user_id = None

            # Try different paths
            if 'entry_data' in shared_data and 'ProfilePage' in shared_data['entry_data']:
                profile_page = shared_data['entry_data']['ProfilePage'][0]

                if 'graphql' in profile_page and 'user' in profile_page['graphql']:
                    user = profile_page['graphql']['user']
                    user_id = user.get('id')

                    if 'edge_owner_to_timeline_media' in user:
                        posts_data = user['edge_owner_to_timeline_media']

            if not posts_data:
                logger.error("Could not locate posts data in HTML")
                return [], None, None

            # Extract posts
            posts = []
            edges = posts_data.get('edges', [])

            for edge in edges:
                node = edge.get('node', {})
                post = self._parse_post_node(node)
                if post:
                    posts.append(post)

            # Get pagination info
            page_info = posts_data.get('page_info', {})
            end_cursor = page_info.get('end_cursor')
            has_next_page = page_info.get('has_next_page', False)

            if not has_next_page:
                end_cursor = None

            logger.info(f"Extracted {len(posts)} initial posts, has_next_page={has_next_page}")

            return posts, end_cursor, user_id

        except Exception as e:
            logger.error(f"Error extracting initial posts: {e}", exc_info=True)
            return [], None, None

    def _parse_post_node(self, node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse a single post node from GraphQL response.

        Args:
            node: Post node data

        Returns:
            Parsed post dict or None
        """
        try:
            post_id = node.get('id')
            shortcode = node.get('shortcode')

            if not post_id or not shortcode:
                logger.warning("Post missing ID or shortcode, skipping")
                return None

            # Determine media type
            typename = node.get('__typename', '')
            is_video = node.get('is_video', False)

            # Extract media URLs
            media_urls = []
            video_url = None

            if typename == 'GraphSidecar':
                # Carousel post (multiple images/videos)
                edges = node.get('edge_sidecar_to_children', {}).get('edges', [])
                for edge in edges:
                    child = edge.get('node', {})
                    if child.get('is_video'):
                        video_url = child.get('video_url')
                        if video_url:
                            media_urls.append(video_url)
                    else:
                        display_url = child.get('display_url')
                        if display_url:
                            media_urls.append(display_url)
            else:
                # Single image or video
                display_url = node.get('display_url')
                if display_url:
                    media_urls.append(display_url)

                if is_video:
                    video_url = node.get('video_url')
                    if video_url and video_url not in media_urls:
                        media_urls.append(video_url)

            # Extract caption
            caption_edges = node.get('edge_media_to_caption', {}).get('edges', [])
            caption = ''
            if caption_edges:
                caption = caption_edges[0].get('node', {}).get('text', '')

            # Extract location
            location = None
            location_data = node.get('location')
            if location_data:
                location = {
                    'id': location_data.get('id'),
                    'name': location_data.get('name'),
                    'slug': location_data.get('slug'),
                }

            # Build post object
            post = {
                'id': post_id,
                'shortcode': shortcode,
                'typename': typename,
                'caption': caption,
                'like_count': node.get('edge_media_preview_like', {}).get('count', 0) or
                             node.get('edge_liked_by', {}).get('count', 0),
                'comment_count': node.get('edge_media_to_comment', {}).get('count', 0) or
                                node.get('edge_media_preview_comment', {}).get('count', 0),
                'view_count': node.get('video_view_count'),
                'timestamp': node.get('taken_at_timestamp'),
                'display_url': node.get('display_url'),
                'media_urls': media_urls,
                'is_video': is_video,
                'video_url': video_url,
                'location': location,
                'permalink': f"https://www.instagram.com/p/{shortcode}/",
                'accessibility_caption': node.get('accessibility_caption'),
                'owner_id': node.get('owner', {}).get('id'),
                'owner_username': node.get('owner', {}).get('username'),
            }

            return post

        except Exception as e:
            logger.error(f"Error parsing post node: {e}", exc_info=True)
            return None

    def _fetch_paginated_posts(
        self,
        user_id: str,
        end_cursor: str,
        posts_per_page: int = 50
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Fetch paginated posts using GraphQL endpoint.

        Args:
            user_id: Instagram user ID
            end_cursor: Pagination cursor
            posts_per_page: Number of posts per page

        Returns:
            Tuple of (posts_list, next_end_cursor)
        """
        try:
            # GraphQL query parameters
            # Note: query_hash may need to be updated if Instagram changes it
            query_hash = self.config.QUERY_HASH_USER_POSTS

            variables = {
                'id': user_id,
                'first': posts_per_page,
                'after': end_cursor
            }

            params = {
                'query_hash': query_hash,
                'variables': json.dumps(variables, separators=(',', ':'))
            }

            # Make GraphQL request
            response = self.client.get(self.config.GRAPHQL_URL, params=params)

            if response.status_code != 200:
                logger.error(f"GraphQL request failed: HTTP {response.status_code}")
                return [], None

            data = response.json()

            # Navigate response structure
            user_data = data.get('data', {}).get('user')
            if not user_data:
                logger.error("No user data in GraphQL response")
                logger.debug(f"GraphQL response structure: {list(data.keys())}")
                logger.debug(f"Full response: {str(data)[:500]}")
                return [], None

            timeline_media = user_data.get('edge_owner_to_timeline_media', {})
            edges = timeline_media.get('edges', [])

            # Parse posts
            posts = []
            for edge in edges:
                node = edge.get('node', {})
                post = self._parse_post_node(node)
                if post:
                    posts.append(post)

            # Get next cursor
            page_info = timeline_media.get('page_info', {})
            next_cursor = page_info.get('end_cursor')
            has_next_page = page_info.get('has_next_page', False)

            if not has_next_page:
                next_cursor = None

            logger.info(f"Fetched {len(posts)} posts, has_next_page={has_next_page}")

            return posts, next_cursor

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GraphQL response: {e}")
            return [], None
        except Exception as e:
            logger.error(f"Error fetching paginated posts: {e}", exc_info=True)
            return [], None

    def scrape_posts(
        self,
        username: str,
        user_id: str,
        profile_user_data: Optional[Dict[str, Any]] = None,
        max_posts: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Scrape posts from a profile. Extracts initial posts from profile data,
        then uses GraphQL API for pagination (requires auth for public accounts).

        Args:
            username: Instagram username
            user_id: User ID from profile data (required)
            profile_user_data: Full user data from profile API (optional)
            max_posts: Maximum number of posts to scrape (None = all)

        Returns:
            List of post dicts
        """
        logger.info(f"Starting posts scrape for @{username} (user_id={user_id})")

        all_posts = []

        try:
            if not user_id:
                logger.error("user_id is required for scraping posts")
                return []

            # Determine max posts to scrape
            max_to_scrape = max_posts or self.config.MAX_POSTS_TO_SCRAPE
            if max_to_scrape == 0:
                max_to_scrape = float('inf')  # Unlimited

            # Extract initial posts from profile API response if available
            end_cursor = None
            if profile_user_data and 'edge_owner_to_timeline_media' in profile_user_data:
                timeline_media = profile_user_data['edge_owner_to_timeline_media']
                edges = timeline_media.get('edges', [])

                logger.info(f"Extracting {len(edges)} posts from profile API response")
                for edge in edges:
                    node = edge.get('node', {})
                    post = self._parse_post_node(node)
                    if post:
                        all_posts.append(post)

                # Get pagination cursor
                page_info = timeline_media.get('page_info', {})
                has_next_page = page_info.get('has_next_page', False)
                if has_next_page:
                    end_cursor = page_info.get('end_cursor')
                    logger.info(f"Profile API indicates more posts available (has_next_page={has_next_page})")
                else:
                    logger.info(f"All posts retrieved from profile API ({len(all_posts)} total)")
                    return all_posts[:max_to_scrape] if max_to_scrape < float('inf') else all_posts

            # Check if we already have enough posts
            if len(all_posts) >= max_to_scrape:
                logger.info(f"Reached max posts limit from profile API: {max_to_scrape}")
                return all_posts[:max_to_scrape]

            # Try to paginate using GraphQL (may require authentication)
            if end_cursor:
                logger.info(f"Attempting to fetch additional posts via GraphQL (may require authentication)...")
                page_num = 1

                try:
                    while len(all_posts) < max_to_scrape and end_cursor:
                        logger.info(f"Fetching page {page_num}, cursor={end_cursor[:20]}...")

                        # Fetch posts page
                        posts, end_cursor = self._fetch_paginated_posts(
                            user_id=user_id,
                            end_cursor=end_cursor,
                            posts_per_page=self.config.POSTS_PER_PAGE
                        )

                        if not posts:
                            logger.info("No more posts available via GraphQL")
                            break

                        all_posts.extend(posts)
                        page_num += 1

                        logger.info(f"Total posts scraped: {len(all_posts)}")

                        # Stop if no more pages
                        if not end_cursor:
                            logger.info("Reached end of posts (no next page)")
                            break

                        # Stop if reached max
                        if len(all_posts) >= max_to_scrape:
                            logger.info(f"Reached max posts limit: {max_to_scrape}")
                            all_posts = all_posts[:max_to_scrape]
                            break

                except Exception as e:
                    logger.warning(f"GraphQL pagination failed (this is expected without authentication): {e}")
                    logger.info(f"Returning {len(all_posts)} posts from profile API only")

            logger.info(f"Successfully scraped {len(all_posts)} posts for @{username}")
            return all_posts

        except Exception as e:
            logger.error(f"Error scraping posts for @{username}: {e}", exc_info=True)
            return all_posts  # Return what we have so far

    def get_post_details(self, shortcode: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a single post.

        Args:
            shortcode: Post shortcode

        Returns:
            Post details dict or None
        """
        try:
            post_url = f"{self.config.BASE_URL}/p/{shortcode}/"
            response = self.client.get(post_url)

            if response.status_code != 200:
                logger.error(f"Failed to fetch post: HTTP {response.status_code}")
                return None

            html = response.text

            # Extract post data (similar to profile extraction)
            match = re.search(r'window\._sharedData\s*=\s*({.+?});</script>', html, re.DOTALL)
            if not match:
                logger.error("Could not extract post data")
                return None

            data = json.loads(match.group(1))
            post_page = data.get('entry_data', {}).get('PostPage', [{}])[0]
            media = post_page.get('graphql', {}).get('shortcode_media', {})

            if not media:
                logger.error("No media data found")
                return None

            post = self._parse_post_node(media)
            return post

        except Exception as e:
            logger.error(f"Error fetching post details: {e}", exc_info=True)
            return None
