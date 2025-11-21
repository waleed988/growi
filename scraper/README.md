# Instagram Profile & Posts Scraper

A production-grade Instagram scraper that extracts public profile data and posts using HTTP requests and JSON/HTML parsing. Built with Python, featuring retry logic, rate limiting, and full pagination support.

## ⚠️ Important Notice (November 2025)

**Instagram now requires authentication** to access profile and post data. As of 2024-2025, Instagram removed `window._sharedData` from public HTML pages.

**To use this scraper, you need:**
- Instagram account (to get session cookies)
- Session cookies from your browser

**Quick Setup:**
1. Login to Instagram in your browser
2. Get `sessionid`, `csrftoken`, and `ds_user_id` cookies (see [QUICK_START_2025.md](QUICK_START_2025.md))
3. Add to `.env` file
4. Run scraper

**See** [QUICK_START_2025.md](QUICK_START_2025.md) **for detailed instructions.**

---

## Features

- **Profile Scraping**: Extract complete profile metadata
- **Post Scraping**: Fetch all posts with full pagination support
- **Media Support**: Handle images, videos, carousels, and reels
- **Robust Architecture**: Retry logic, rate limiting, and error handling
- **Anti-Blocking**: User-agent rotation, proxy support, and request throttling
- **Multiple Output Formats**: JSON and CSV export
- **Production-Ready**: Comprehensive logging, configuration management, and security measures

## Requirements

- Python 3.8 or higher
- pip (Python package manager)

## Installation

### 1. Clone or Download Repository

```bash
cd scraper
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configuration (Optional)

Copy the example environment file and customize settings:

```bash
cp .env.example .env
```

Edit `.env` to configure:
- Request timeouts and retries
- Rate limiting parameters
- Proxy settings
- Output preferences
- Logging level

## Quick Start

### Basic Usage

Scrape a profile and all its posts:

```bash
python main.py username
```

Example:
```bash
python main.py cristiano
```

### Scrape Limited Posts

Scrape profile and first 50 posts:

```bash
python main.py username --max-posts 50
```

### Profile Only

Scrape only profile data (no posts):

```bash
python main.py username --profile-only
```

### Export to CSV

Export posts to CSV format:

```bash
python main.py username --output csv
```

### Debug Mode

Enable debug logging for troubleshooting:

```bash
python main.py username --log-level DEBUG
```

## Command-Line Options

```
usage: main.py [-h] [--max-posts MAX_POSTS] [--profile-only]
               [--output {json,csv,both}] [--log-level {DEBUG,INFO,WARNING,ERROR}]
               [--version]
               username

positional arguments:
  username              Instagram username to scrape (without @)

optional arguments:
  -h, --help            Show this help message and exit
  --max-posts MAX_POSTS Maximum number of posts to scrape (default: all)
  --profile-only        Scrape only profile data, skip posts
  --output {json,csv,both}
                        Output format (default: json)
  --log-level {DEBUG,INFO,WARNING,ERROR}
                        Logging level (default: INFO)
  --version             Show program version and exit
```

## Output

### Output Directory

All scraped data is saved to the `./output` directory by default.

### JSON Output Format

```json
{
  "profile": {
    "username": "username",
    "full_name": "Full Name",
    "biography": "Bio text...",
    "follower_count": 12345,
    "following_count": 678,
    "posts_count": 90,
    "profile_pic_url": "https://...",
    "profile_pic_url_hd": "https://...",
    "is_verified": true,
    "is_business_account": false,
    "is_professional_account": false,
    "is_private": false,
    "category": "Category Name",
    "external_url": "https://...",
    "scraped_at": "2025-11-21T16:30:00Z",
    "scraper_version": "1.0.0"
  },
  "posts": [
    {
      "id": "1234567890",
      "shortcode": "ABC123",
      "typename": "GraphImage",
      "caption": "Post caption...",
      "like_count": 5000,
      "comment_count": 250,
      "view_count": null,
      "timestamp": 1700000000,
      "display_url": "https://...",
      "media_urls": ["https://..."],
      "is_video": false,
      "video_url": null,
      "location": {
        "id": "123",
        "name": "Location Name",
        "slug": "location-slug"
      },
      "permalink": "https://www.instagram.com/p/ABC123/",
      "accessibility_caption": "Image description",
      "owner_id": "987654321",
      "owner_username": "username"
    }
  ],
  "metadata": {
    "total_posts_scraped": 50,
    "scrape_completed_at": "2025-11-21T16:35:00Z",
    "scraper_version": "1.0.0"
  }
}
```

### Output Files

For each scrape, two files are created:

1. **Timestamped File**: `username_YYYYMMDD_HHMMSS.json`
2. **Latest File**: `username_latest.json` (overwritten each time)

## Configuration

### Environment Variables

All configuration can be done via `.env` file:

```bash
# Request Configuration
REQUEST_TIMEOUT=30            # Request timeout in seconds
MAX_RETRIES=5                 # Maximum retry attempts
RETRY_BACKOFF_FACTOR=2.0      # Exponential backoff multiplier

# Rate Limiting
MIN_DELAY=2.0                 # Minimum delay between requests (seconds)
MAX_DELAY=5.0                 # Maximum delay between requests (seconds)

# Pagination
POSTS_PER_PAGE=50             # Posts to fetch per GraphQL request
MAX_POSTS_TO_SCRAPE=0         # 0 = unlimited

# Proxy Settings
USE_PROXIES=false             # Enable proxy rotation
PROXY_LIST=http://proxy1.com:8080,http://proxy2.com:8080
PROXY_ROTATION=true           # Rotate through proxy list

# User-Agent Settings
ROTATE_USER_AGENTS=true       # Rotate user agents
CUSTOM_USER_AGENT=            # Force specific user agent (optional)

# Output Settings
OUTPUT_DIR=./output           # Output directory path
SAVE_RAW_HTML=false           # Save raw HTML for debugging
PRETTY_PRINT_JSON=true        # Pretty print JSON output

# Logging
LOG_LEVEL=INFO                # DEBUG, INFO, WARNING, ERROR
LOG_FILE=                     # Optional log file path

# Security
VERIFY_SSL=true               # Verify SSL certificates
```

## Data Collected

### Profile Fields

- username
- full_name
- biography
- follower_count
- following_count
- posts_count
- profile_pic_url
- profile_pic_url_hd
- is_verified
- is_business_account
- is_professional_account
- is_private
- category
- external_url

### Post Fields

- id
- shortcode
- typename (GraphImage, GraphVideo, GraphSidecar)
- caption
- like_count
- comment_count
- view_count (videos only)
- timestamp
- display_url
- media_urls (array - all images/videos)
- is_video
- video_url
- location (if available)
- permalink
- accessibility_caption
- owner_id
- owner_username

## Features in Detail

### Retry Logic

- Automatic retry on network errors
- Exponential backoff (2, 4, 8, 16, 32 seconds)
- Configurable max retries (default: 5)
- Smart error detection (rate limits, bans, timeouts)

### Rate Limiting

- Random delays between requests (2-5 seconds default)
- Prevents Instagram rate limiting
- Configurable via environment variables
- Adaptive throttling on errors

### Anti-Blocking Measures

- User-agent rotation (50+ agents)
- Proxy rotation support (with health checks)
- Session management
- Request header randomization
- Ban detection and handling

### Pagination

- Automatic pagination through all posts
- Uses Instagram's GraphQL API
- Configurable posts per page
- Progress logging
- Resumable scraping (maintains state)

### Error Handling

- Network error recovery
- HTTP error handling
- Parsing error fallbacks
- Graceful degradation
- Detailed error logging

## Troubleshooting

### Rate Limited / Banned

If you encounter rate limiting:

1. Increase delays in `.env`:
   ```
   MIN_DELAY=5.0
   MAX_DELAY=10.0
   ```

2. Enable proxy rotation:
   ```
   USE_PROXIES=true
   PROXY_LIST=http://proxy1:port,http://proxy2:port
   ```

3. Wait 15-30 minutes before retrying

### No Data Extracted

If scraping returns empty data:

1. Check if account exists and is public
2. Enable debug logging:
   ```bash
   python main.py username --log-level DEBUG
   ```
3. Save raw HTML for inspection:
   ```
   SAVE_RAW_HTML=true
   ```

### Private Accounts

Private accounts only return profile data. Posts cannot be scraped without authentication.

### GraphQL Query Hash Changed

If Instagram changes their GraphQL query hashes:

1. Update `QUERY_HASH_USER_POSTS` in `config/settings.py`
2. Find new hash by inspecting Instagram's network requests in browser DevTools

## Architecture

```
scraper/
├── main.py                 # Entry point and CLI
├── requirements.txt        # Python dependencies
├── .env.example           # Configuration template
│
├── config/
│   ├── __init__.py
│   └── settings.py        # Configuration management
│
├── modules/
│   ├── __init__.py
│   ├── profile_scraper.py # Profile data extraction
│   └── posts_scraper.py   # Posts scraping with pagination
│
├── utils/
│   ├── __init__.py
│   ├── http_client.py     # HTTP client with retry logic
│   ├── logger.py          # Logging configuration
│   └── output_formatter.py # JSON/CSV output formatting
│
└── output/                # Scraped data output directory
```

## Security Considerations

- **No Authentication**: Only scrapes public data
- **Rate Limiting**: Respects Instagram's resources
- **SSL Verification**: Enabled by default
- **Input Validation**: Sanitizes usernames
- **No Credentials**: Never stores or transmits credentials
- **Proxy Security**: Supports authenticated proxies

## Limitations

- Can only scrape **public** accounts
- Subject to Instagram's rate limits
- GraphQL query hashes may change over time
- No authentication or API access
- Cannot scrape stories, highlights, or DMs

## Legal & Ethical Use

This tool is for educational and research purposes only. Users are responsible for:

- Complying with Instagram's Terms of Service
- Respecting data privacy and intellectual property
- Not using scraped data for malicious purposes
- Following applicable laws and regulations

**Use responsibly and ethically.**

## Performance

### Expected Throughput

- Profile scraping: ~5-10 profiles/minute
- Posts scraping: ~50-100 posts/minute
- 200-post account: ~3-5 minutes total

### Resource Usage

- Memory: ~50-100 MB
- CPU: Low (mostly I/O bound)
- Network: ~1-5 MB per account (depends on posts)

## Support

### Issues

If you encounter issues:

1. Check logs with `--log-level DEBUG`
2. Review [Troubleshooting](#troubleshooting) section
3. Ensure dependencies are up to date
4. Check Instagram hasn't changed their structure

### Version

Current version: **1.0.0**

Check version:
```bash
python main.py --version
```

## License

This project is provided as-is for educational purposes.

## Changelog

### v1.0.0 (2025-11-21)
- Initial release
- Profile scraping
- Posts scraping with pagination
- Retry logic and rate limiting
- Proxy rotation support
- JSON/CSV output
- Comprehensive logging

---

**Built with Python 3.8+ | Production-Grade Architecture | Ethical Scraping**
