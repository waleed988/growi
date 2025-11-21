# Instagram Raw Data Acquisition System - Architecture Design

## Executive Summary

This document describes a production-grade, scalable architecture for continuously acquiring raw data from Instagram public profiles and posts. The system is designed to handle thousands of accounts while maintaining reliability, avoiding detection, and ensuring data quality.

---

## 1. Data Access Strategy

### A. Primary Data Sources

**Instagram Public Endpoints (No Authentication Required)**

1. **Profile HTML Pages**
   - URL: `https://www.instagram.com/{username}/`
   - Contains embedded JSON in `window._sharedData` or `window.__additionalDataLoaded()`
   - Includes: profile metadata, first 12 posts, GraphQL query hashes

2. **GraphQL API Endpoints**
   - URL: `https://www.instagram.com/graphql/query/`
   - Used for: Post pagination, profile data, media details
   - Requires: Query hash, variables (user_id, end_cursor, first)
   - Returns: JSON responses with post data

3. **Data Extraction Method**
   ```
   HTTP Request → HTML Response → Parse Embedded JSON → Extract Data
                                 → GraphQL Query → Paginated Posts
   ```

### B. Session Management

- **Cookies**: Essential for maintaining session state
  - `sessionid`, `csrftoken`, `ds_user_id`
  - Obtained from initial profile page visit
  - Rotated when rate limits detected

- **Headers**: Mimic legitimate browser requests
  - User-Agent rotation (Chrome, Firefox, Safari)
  - Accept, Accept-Language, Referer headers
  - X-CSRFToken, X-IG-App-ID headers

---

## 2. Scraper System Architecture

### A. High-Level System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    Discovery Layer                           │
│  (Hashtag tracking, Related accounts, Manual input)          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Job Queue & Scheduler                       │
│  • Redis/RabbitMQ for job distribution                      │
│  • Priority queues (high-value accounts first)              │
│  • Schedule: Daily profiles, Hourly new posts               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Worker Pool (Scrapers)                     │
│  • Multiple Python workers (5-50 depending on proxies)      │
│  • Each worker: Fetch → Parse → Validate → Store            │
│  • Rate limiting: 5-10 requests/min per worker              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Storage Layer                        │
│  • Raw JSON storage (S3/MongoDB)                            │
│  • Metadata database (PostgreSQL)                           │
│  • Cache layer (Redis) for recent data                      │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Monitoring & Alerting                       │
│  • Success/failure rates, Ban detection, Queue depth        │
└─────────────────────────────────────────────────────────────┘
```

### B. Worker Scraper Structure

**Module Breakdown:**

1. **HTTP Client Module** (`http_client.py`)
   - Manages requests with retry logic
   - Session persistence and rotation
   - Proxy rotation
   - User-agent rotation
   - Rate limiting (exponential backoff)

2. **Profile Scraper Module** (`profile_scraper.py`)
   - Fetches profile HTML
   - Parses embedded JSON
   - Extracts profile fields
   - Validates data completeness

3. **Posts Scraper Module** (`posts_scraper.py`)
   - Fetches initial posts from profile page
   - Queries GraphQL for pagination
   - Handles all media types (image, carousel, video, reel)
   - Extracts post metadata

4. **Data Validator Module** (`validator.py`)
   - Ensures all required fields present
   - Data type validation
   - Sanitizes outputs

5. **Storage Module** (`storage.py`)
   - JSON serialization
   - File/database writes
   - Deduplication

### C. Retry & Error Handling Strategy

**Retry Logic:**
```python
Max Retries: 5
Backoff: Exponential (2^attempt seconds)
Retry Conditions:
  - Network errors (ConnectionError, Timeout)
  - HTTP 500, 502, 503 errors
  - Parsing errors (retry with different approach)

No Retry Conditions:
  - HTTP 404 (account doesn't exist)
  - HTTP 403 (private account)
  - Invalid username format
```

**Ban Detection & Response:**
- **Indicators**:
  - HTTP 429 (Rate Limit)
  - HTTP 302 redirect to login
  - Challenge pages (CAPTCHA)
  - Empty response bodies
  - Consistent failures across accounts

- **Response Actions**:
  1. Immediate: Wait 60+ seconds, switch proxy
  2. If persists: Rotate session cookies
  3. If persists: Mark proxy as banned (cooldown 1 hour)
  4. If all proxies banned: Alert ops team, pause worker

### D. Proxy Rotation Strategy

**Proxy Pool Management:**
- **Proxy Types**: Residential > Datacenter > Free (in order of preference)
- **Pool Size**: Minimum 20-50 proxies for production
- **Rotation Logic**:
  - Round-robin for normal requests
  - Immediate switch on rate limit
  - Health checks every 5 minutes
  - Remove dead proxies automatically

**Proxy Configuration:**
```python
{
  "proxy_url": "http://user:pass@proxy.com:8080",
  "success_count": 1250,
  "failure_count": 5,
  "last_used": "2025-11-21T16:30:00Z",
  "status": "active",  # active, cooldown, banned
  "cooldown_until": null
}
```

### E. User-Agent Strategy

**Rotation Approach:**
- Pool of 50+ realistic user agents
- Mix of Chrome (70%), Firefox (20%), Safari (10%)
- Desktop only (mobile user-agents behave differently)
- Consistent user-agent per session (don't mix mid-session)
- Automatic updates monthly (match latest browser versions)

---

## 3. Raw Data Collection Specification

### A. Profile Data Schema

```json
{
  "username": "string",
  "full_name": "string",
  "biography": "string",
  "follower_count": "integer",
  "following_count": "integer",
  "posts_count": "integer",
  "profile_pic_url": "string (URL)",
  "profile_pic_url_hd": "string (URL)",
  "is_verified": "boolean",
  "is_business_account": "boolean",
  "is_professional_account": "boolean",
  "category": "string | null",
  "external_url": "string (URL) | null",
  "is_private": "boolean",
  "scraped_at": "ISO 8601 timestamp",
  "scraper_version": "string"
}
```

### B. Posts Data Schema

```json
{
  "id": "string",
  "shortcode": "string",
  "typename": "string (GraphImage, GraphVideo, GraphSidecar)",
  "caption": "string | null",
  "like_count": "integer",
  "comment_count": "integer",
  "view_count": "integer | null (video only)",
  "timestamp": "integer (Unix timestamp)",
  "taken_at_timestamp": "integer",
  "display_url": "string (URL)",
  "media_urls": ["array of URLs"],
  "is_video": "boolean",
  "video_url": "string (URL) | null",
  "location": {
    "id": "string",
    "name": "string",
    "slug": "string"
  } | null,
  "permalink": "string (https://www.instagram.com/p/{shortcode}/)",
  "accessibility_caption": "string | null",
  "owner_id": "string",
  "owner_username": "string"
}
```

### C. Carousel Posts (Multi-Image)

For `GraphSidecar` posts:
```json
{
  "typename": "GraphSidecar",
  "carousel_media": [
    {
      "id": "string",
      "display_url": "string",
      "is_video": "boolean",
      "video_url": "string | null"
    }
  ]
}
```

---

## 4. Scheduling & Frequency Strategy

### A. Scraping Intervals

**Profile Data:**
- **High-Value Accounts** (100k+ followers): Every 6 hours
- **Medium Accounts** (10k-100k): Daily
- **Low-Activity Accounts**: Every 3 days
- **New Accounts**: Immediate scrape, then daily for 1 week

**Posts Data:**
- **Active Accounts** (posts daily): Every 4 hours
- **Normal Accounts**: Every 12 hours
- **Inactive Accounts**: Daily check for new posts

**Priority Queue Logic:**
```
Priority = (follower_count / 1000) + (posts_per_day * 10) + (is_verified * 50)
```

### B. Job Scheduling Architecture

```python
Job Queue Structure:
- high_priority_queue (celebrities, brands)
- normal_queue (regular accounts)
- retry_queue (failed jobs with backoff)
- discovery_queue (new accounts to scrape)

Scheduler Cron Jobs:
- Every hour: Process high_priority_queue
- Every 6 hours: Process normal_queue
- Every day: Clean old data, update priorities
```

### C. Resource Allocation

```
Workers per Queue:
- 10 workers on high_priority_queue
- 20 workers on normal_queue
- 5 workers on retry_queue
- 5 workers on discovery_queue

Expected Throughput:
- 5-10 requests/minute/worker = 200-400 req/min total
- ~15-30 profiles/hour/worker = 600-1200 profiles/hour
- ~50-100 posts/hour/worker (with pagination)
```

---

## 5. Anti-Blocking & Resilience Measures

### A. Rate Limiting

**Request Throttling:**
- 5-10 requests per minute per worker
- Random delays between requests (2-5 seconds)
- Respect Instagram's rate limits
- Adaptive rate limiting (slow down if errors increase)

**Circuit Breaker Pattern:**
- If failure rate > 30% for 5 minutes → Pause worker
- Cooldown period: 15 minutes
- Gradual ramp-up after recovery

### B. Session Rotation

- New session every 100 requests
- Cookie refresh every 30 minutes
- Clear session on ban detection
- Session pool (pre-warmed sessions ready to use)

### C. Request Randomization

- Random sleep between requests (2-5s)
- Random order of profile visits
- Mimic human behavior (scroll pattern in pagination)
- Avoid predictable patterns

### D. Monitoring & Alerts

**Key Metrics:**
- Success rate (target: >95%)
- Average response time
- Ban detection count
- Queue depth
- Proxy health

**Alerts:**
- Success rate drops below 80%
- All proxies in cooldown
- Queue depth exceeds 10,000 jobs
- Worker crashes

---

## 6. Scalability & Performance Optimization

### A. Horizontal Scaling

- **Stateless Workers**: Easy to add more workers
- **Distributed Queue**: Redis/RabbitMQ supports multiple consumers
- **Cloud Deployment**: AWS ECS/Kubernetes for auto-scaling

### B. Caching Strategy

- **Cache Recent Profiles**: TTL 6 hours (avoid re-scraping)
- **Cache GraphQL Query Hashes**: Update daily
- **Cache Proxy Health**: Check every 5 minutes

### C. Database Optimization

- **Indexes**: On username, timestamp, scrape_status
- **Partitioning**: By date (monthly partitions)
- **Archival**: Move data >90 days to cold storage (S3 Glacier)

### D. Cost Optimization

- **Smart Scheduling**: Don't re-scrape unchanged accounts
- **Delta Updates**: Only scrape new posts since last check
- **Proxy Pooling**: Share proxies across workers efficiently

---

## 7. Security & Compliance

### A. Security Best Practices

- **No Credentials Storage**: Only scrape public data
- **Encrypted Proxy Configs**: Don't expose proxy credentials
- **Secure API Keys**: Environment variables, not hardcoded
- **Input Validation**: Sanitize usernames to prevent injection

### B. Legal & Ethical Considerations

- **Public Data Only**: No authentication, no private accounts
- **Rate Limiting**: Respect Instagram's resources
- **robots.txt**: Acknowledge (though not strictly applicable)
- **Terms of Service**: Be aware of Instagram's ToS

### C. Data Privacy

- **PII Handling**: Treat scraped data as potentially sensitive
- **Data Retention**: Clear policies on how long to keep data
- **User Deletion Requests**: Mechanism to remove data if requested

---

## 8. System Maintainability

### A. Code Quality

- **Modular Design**: Separate concerns (scraping, parsing, storage)
- **Type Hints**: Use Python type annotations
- **Unit Tests**: 80%+ coverage target
- **Logging**: Structured logging (JSON format)

### B. Configuration Management

- **Environment-Based Configs**: Dev, staging, production
- **Secrets Management**: AWS Secrets Manager / HashiCorp Vault
- **Feature Flags**: Enable/disable features without deployment

### C. Monitoring & Debugging

- **Distributed Tracing**: Track requests across services
- **Log Aggregation**: ELK stack or CloudWatch
- **Metrics Dashboard**: Grafana for real-time monitoring
- **Error Tracking**: Sentry for exception monitoring

---

## 9. Future Enhancements

### A. Advanced Features

1. **Story Scraping**: Ephemeral content (24-hour window)
2. **Comment Scraping**: Extract comments from posts
3. **Hashtag Tracking**: Monitor trending hashtags
4. **IGTV/Reels**: Extended video content
5. **Live Detection**: Detect when accounts go live

### B. ML/AI Integration

1. **Account Quality Scoring**: ML model to prioritize accounts
2. **Content Classification**: Auto-categorize posts
3. **Ban Prediction**: Predict when bans might occur
4. **Anomaly Detection**: Detect unusual patterns

### C. Infrastructure Evolution

1. **Multi-Region Deployment**: Reduce latency, improve resilience
2. **Kafka Event Streaming**: Real-time data pipeline
3. **GraphQL Federation**: Unified API layer
4. **Serverless Functions**: AWS Lambda for on-demand scraping

---

## 10. Conclusion

This architecture provides a robust, scalable foundation for continuously acquiring Instagram raw data. Key strengths:

- **Reliability**: Multi-layer retry logic, health checks, monitoring
- **Scalability**: Horizontal scaling, distributed queues, stateless workers
- **Anti-Blocking**: Proxy rotation, session management, rate limiting
- **Maintainability**: Modular design, comprehensive logging, automated testing

The system is designed to handle thousands of accounts while maintaining a >95% success rate and avoiding detection.

---

**Document Version**: 1.0
**Last Updated**: 2025-11-21
**Author**: Instagram Scraper Team
