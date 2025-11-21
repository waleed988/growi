#!/usr/bin/env python3
"""
Instagram Scraper - Main Entry Point
Scrapes public Instagram profiles and posts with pagination support.
"""

import sys
import argparse
import logging
from typing import Optional

from utils.logger import setup_logger
from utils.http_client import HTTPClient
from utils.output_formatter import OutputFormatter
from modules.profile_scraper import ProfileScraper
from modules.posts_scraper import PostsScraper
from config.settings import ScraperConfig

# Setup logger
logger = setup_logger()


class InstagramScraper:
    """Main orchestrator for Instagram scraping operations."""

    def __init__(self):
        """Initialize scraper components."""
        self.http_client = HTTPClient()
        self.profile_scraper = ProfileScraper(self.http_client)
        self.posts_scraper = PostsScraper(self.http_client)
        self.output_formatter = OutputFormatter()
        self.config = ScraperConfig

        logger.info(f"Instagram Scraper v{self.config.SCRAPER_VERSION} initialized")

    def scrape_account(
        self,
        username: str,
        max_posts: Optional[int] = None,
        output_format: str = 'json'
    ) -> bool:
        """
        Scrape complete account data (profile + posts).

        Args:
            username: Instagram username
            max_posts: Maximum number of posts to scrape (None = all)
            output_format: Output format ('json' or 'csv')

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Starting scrape for @{username}")

        try:
            # Step 1: Scrape profile data
            logger.info("Step 1/2: Scraping profile data...")
            profile = self.profile_scraper.scrape_profile(username)

            if not profile:
                logger.error("Failed to scrape profile data")
                return False

            logger.info(f"Profile scraped successfully: @{profile['username']}")

            # Check if account is private
            if profile.get('is_private'):
                logger.warning(f"Account @{username} is private. Cannot scrape posts.")
                print(f"\n⚠️  Account @{username} is private. Only profile data was scraped.\n")

                # Save profile only
                self.output_formatter.save_to_json(
                    {'profile': profile, 'posts': [], 'metadata': {'note': 'Private account'}},
                    f"{username}_profile_only.json"
                )
                return True

            # Step 2: Scrape posts with pagination
            logger.info("Step 2/2: Scraping posts with pagination...")
            posts = self.posts_scraper.scrape_posts(
                username=username,
                max_posts=max_posts
            )

            logger.info(f"Successfully scraped {len(posts)} posts")

            # Step 3: Format and save output
            logger.info("Formatting and saving output...")

            if output_format == 'json':
                output_path = self.output_formatter.save_profile_and_posts(
                    profile=profile,
                    posts=posts,
                    username=username
                )
                logger.info(f"Data saved to: {output_path}")

            if output_format == 'csv' or output_format == 'both':
                csv_path = self.output_formatter.export_csv(
                    posts=posts,
                    filename=f"{username}_posts.csv"
                )
                logger.info(f"CSV exported to: {csv_path}")

            # Print summary
            self.output_formatter.print_summary(profile, posts)

            logger.info(f"Scraping completed successfully for @{username}")
            return True

        except KeyboardInterrupt:
            logger.warning("Scraping interrupted by user")
            print("\n\n⚠️  Scraping interrupted. Partial data may have been saved.\n")
            return False

        except Exception as e:
            logger.error(f"Error during scraping: {e}", exc_info=True)
            return False

        finally:
            # Cleanup
            self.http_client.close()

    def scrape_profile_only(self, username: str) -> bool:
        """
        Scrape only profile data (no posts).

        Args:
            username: Instagram username

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Scraping profile only for @{username}")

        try:
            profile = self.profile_scraper.scrape_profile(username)

            if not profile:
                logger.error("Failed to scrape profile")
                return False

            # Save profile data
            self.output_formatter.save_to_json(
                {'profile': profile, 'posts': []},
                f"{username}_profile.json"
            )

            # Print profile info
            print(f"\n{'='*60}")
            print(f"Profile: @{profile['username']}")
            print(f"Name: {profile['full_name']}")
            print(f"Followers: {profile['follower_count']:,}")
            print(f"Following: {profile['following_count']:,}")
            print(f"Posts: {profile['posts_count']:,}")
            print(f"{'='*60}\n")

            return True

        except Exception as e:
            logger.error(f"Error scraping profile: {e}", exc_info=True)
            return False

        finally:
            self.http_client.close()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Instagram Profile & Posts Scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape profile and all posts
  python main.py lilbieber

  # Scrape profile and first 50 posts
  python main.py lilbieber --max-posts 50

  # Scrape profile only (no posts)
  python main.py lilbieber --profile-only

  # Export to CSV format
  python main.py lilbieber --output csv

  # Enable debug logging
  python main.py lilbieber --log-level DEBUG

Environment Variables:
  See .env.example for configuration options
        """
    )

    parser.add_argument(
        'username',
        help='Instagram username to scrape (without @)'
    )

    parser.add_argument(
        '--max-posts',
        type=int,
        default=None,
        help='Maximum number of posts to scrape (default: all posts)'
    )

    parser.add_argument(
        '--profile-only',
        action='store_true',
        help='Scrape only profile data, skip posts'
    )

    parser.add_argument(
        '--output',
        choices=['json', 'csv', 'both'],
        default='json',
        help='Output format (default: json)'
    )

    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )

    parser.add_argument(
        '--version',
        action='version',
        version=f'Instagram Scraper v{ScraperConfig.SCRAPER_VERSION}'
    )

    args = parser.parse_args()

    # Update log level if specified
    if args.log_level:
        logger.setLevel(getattr(logging, args.log_level))
        logger.info(f"Log level set to {args.log_level}")

    # Print banner
    print("\n" + "=" * 60)
    print(f"Instagram Scraper v{ScraperConfig.SCRAPER_VERSION}")
    print("=" * 60 + "\n")

    # Create scraper instance
    scraper = InstagramScraper()

    # Execute scraping
    try:
        if args.profile_only:
            success = scraper.scrape_profile_only(args.username)
        else:
            success = scraper.scrape_account(
                username=args.username,
                max_posts=args.max_posts,
                output_format=args.output
            )

        if success:
            print("\n✅ Scraping completed successfully!\n")
            sys.exit(0)
        else:
            print("\n❌ Scraping failed. Check logs for details.\n")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Exiting...\n")
        sys.exit(130)

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\n❌ Error: {e}\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
