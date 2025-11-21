"""
Output formatter for scraped Instagram data.
Handles JSON serialization and file output.
"""

import json
import os
import logging
from typing import Dict, Any, List
from datetime import datetime

from config.settings import ScraperConfig

logger = logging.getLogger(__name__)


class OutputFormatter:
    """Formatter for scraped data output."""

    def __init__(self):
        """Initialize output formatter."""
        self.config = ScraperConfig

        # Ensure output directory exists
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)

    def format_output(
        self,
        profile: Dict[str, Any],
        posts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Format scraped data into standardized output structure.

        Args:
            profile: Profile data dict
            posts: List of post dicts

        Returns:
            Formatted output dict
        """
        output = {
            'profile': profile,
            'posts': posts,
            'metadata': {
                'total_posts_scraped': len(posts),
                'scrape_completed_at': datetime.utcnow().isoformat() + 'Z',
                'scraper_version': self.config.SCRAPER_VERSION,
            }
        }

        return output

    def save_to_json(
        self,
        data: Dict[str, Any],
        filename: str,
        pretty: bool = None
    ) -> str:
        """
        Save data to JSON file.

        Args:
            data: Data to save
            filename: Output filename (without path)
            pretty: Pretty print JSON (default from config)

        Returns:
            Full path to saved file
        """
        # Use config setting if not specified
        if pretty is None:
            pretty = self.config.PRETTY_PRINT_JSON

        # Build full path
        if not filename.endswith('.json'):
            filename += '.json'

        filepath = os.path.join(self.config.OUTPUT_DIR, filename)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                if pretty:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                else:
                    json.dump(data, f, ensure_ascii=False)

            file_size = os.path.getsize(filepath)
            logger.info(f"Saved output to {filepath} ({file_size:,} bytes)")

            return filepath

        except Exception as e:
            logger.error(f"Failed to save JSON file: {e}")
            raise

    def save_profile_and_posts(
        self,
        profile: Dict[str, Any],
        posts: List[Dict[str, Any]],
        username: str
    ) -> str:
        """
        Save profile and posts to JSON file with timestamp.

        Args:
            profile: Profile data
            posts: Posts data
            username: Instagram username

        Returns:
            Path to saved file
        """
        # Format output
        output = self.format_output(profile, posts)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{username}_{timestamp}.json"

        # Save to file
        filepath = self.save_to_json(output, filename)

        # Also save as latest (without timestamp)
        latest_filename = f"{username}_latest.json"
        self.save_to_json(output, latest_filename)

        return filepath

    def print_summary(
        self,
        profile: Dict[str, Any],
        posts: List[Dict[str, Any]]
    ) -> None:
        """
        Print summary of scraped data to console.

        Args:
            profile: Profile data
            posts: Posts data
        """
        print("\n" + "=" * 60)
        print("SCRAPING SUMMARY")
        print("=" * 60)

        print(f"\nProfile: @{profile.get('username')}")
        print(f"Full Name: {profile.get('full_name')}")
        print(f"Followers: {profile.get('follower_count'):,}")
        print(f"Following: {profile.get('following_count'):,}")
        print(f"Total Posts: {profile.get('posts_count'):,}")
        print(f"Verified: {'Yes' if profile.get('is_verified') else 'No'}")
        print(f"Private: {'Yes' if profile.get('is_private') else 'No'}")

        if profile.get('biography'):
            bio = profile['biography'][:100]
            if len(profile['biography']) > 100:
                bio += "..."
            print(f"Bio: {bio}")

        print(f"\n{'='*60}")
        print(f"Posts Scraped: {len(posts)}")

        if posts:
            total_likes = sum(p.get('like_count', 0) for p in posts)
            total_comments = sum(p.get('comment_count', 0) for p in posts)
            video_posts = sum(1 for p in posts if p.get('is_video'))
            carousel_posts = sum(1 for p in posts if p.get('typename') == 'GraphSidecar')

            print(f"Total Likes: {total_likes:,}")
            print(f"Total Comments: {total_comments:,}")
            print(f"Video Posts: {video_posts}")
            print(f"Carousel Posts: {carousel_posts}")

            if posts:
                avg_likes = total_likes / len(posts)
                avg_comments = total_comments / len(posts)
                print(f"Average Likes per Post: {avg_likes:.1f}")
                print(f"Average Comments per Post: {avg_comments:.1f}")

        print("=" * 60 + "\n")

    def export_csv(
        self,
        posts: List[Dict[str, Any]],
        filename: str
    ) -> str:
        """
        Export posts to CSV format (optional feature).

        Args:
            posts: List of posts
            filename: Output filename

        Returns:
            Path to saved file
        """
        import csv

        if not filename.endswith('.csv'):
            filename += '.csv'

        filepath = os.path.join(self.config.OUTPUT_DIR, filename)

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                if not posts:
                    logger.warning("No posts to export")
                    return filepath

                # Define CSV columns
                fieldnames = [
                    'id', 'shortcode', 'permalink', 'timestamp',
                    'like_count', 'comment_count', 'view_count',
                    'is_video', 'typename', 'caption'
                ]

                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()

                for post in posts:
                    # Truncate caption for CSV
                    if post.get('caption'):
                        post['caption'] = post['caption'][:500]

                    writer.writerow(post)

            logger.info(f"Exported {len(posts)} posts to CSV: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Failed to export CSV: {e}")
            raise
