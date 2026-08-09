import feedparser
import httpx
import logging
import re
import random
import time
import calendar
from typing import List, Dict, Any, Optional

NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://rsshub.rssforever.com/twitter/user",
    "https://rsshub.app/twitter/user"
]

class PostItem:
    def __init__(self, post_id: str, author: str, content: str, url: str, published_at: str = "", published_timestamp: float = 0.0, is_retweet: bool = False, media_urls: Optional[List[str]] = None):
        self.post_id = post_id
        self.author = author
        self.content = content
        self.url = url
        self.published_at = published_at
        self.published_timestamp = published_timestamp
        self.is_retweet = is_retweet
        self.media_urls = media_urls or []

    def is_older_than_hours(self, max_hours: float) -> bool:
        if self.published_timestamp <= 0.0:
            return False
        age_seconds = time.time() - self.published_timestamp
        return age_seconds > (max_hours * 3600)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "post_id": self.post_id,
            "author": self.author,
            "content": self.content,
            "url": self.url,
            "published_at": self.published_at,
            "published_timestamp": self.published_timestamp,
            "is_retweet": self.is_retweet,
            "media_urls": self.media_urls
        }

class SocialMonitor:
    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    def clean_html(self, raw_html: str) -> str:
        """Loại bỏ các thẻ HTML để lấy văn bản thuần."""
        cleanr = re.compile('<.*?>')
        cleantext = re.sub(cleanr, '', raw_html)
        return cleantext.strip()

    def is_original_post(self, title_or_content: str) -> bool:
        """Kiểm tra xem bài đăng có phải là bài gốc không (loại bỏ RT / Retweet / Reply)."""
        text = title_or_content.strip()
        if text.startswith("RT @") or text.startswith("R to @") or text.startswith("Retweeting @"):
            return False
        return True

    def fetch_x_account_posts(self, username: str, collect_media: bool = False) -> tuple[List[PostItem], Optional[str]]:
        """
        Thử cào bài viết gốc mới từ tài khoản X (Twitter) qua các nguồn RSS/Nitter instance.
        """
        username = username.strip().lstrip("@")
        if not username:
            return [], "Tên tài khoản không hợp lệ"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        # Shuffle instances slightly to balance load
        instances = NITTER_INSTANCES.copy()
        
        errors = []
        for instance in instances:
            feed_url = f"{instance}/{username}/rss" if "rsshub" not in instance else f"{instance}/{username}"
            try:
                # Add random jitter delay to prevent rate limits
                time.sleep(random.uniform(0.2, 0.5))

                with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
                    resp = client.get(feed_url)
                    if resp.status_code == 200:
                        feed = feedparser.parse(resp.text)
                        if feed.entries:
                            posts = []
                            for entry in feed.entries:
                                raw_summary = entry.get("summary") or entry.get("title") or ""
                                clean_summary = self.clean_html(raw_summary)

                                # Filter: Only original posts as requested
                                if not self.is_original_post(clean_summary):
                                    continue

                                raw_id = entry.get("id") or entry.get("link") or entry.get("guid") or ""
                                status_match = re.search(r'/status/(\d+)', raw_id)
                                if status_match:
                                    post_id = f"x_status_{status_match.group(1)}"
                                else:
                                    post_id = raw_id

                                link = entry.get("link", f"https://x.com/{username}")
                                if "nitter" in link:
                                    link = re.sub(r'https?://[^/]+', 'https://x.com', link)

                                # Extract media links if requested
                                media_urls = []
                                if collect_media and "media_content" in entry:
                                    for m in entry.media_content:
                                        if "url" in m:
                                            media_urls.append(m["url"])

                                # Extract published timestamp (using calendar.timegm for UTC)
                                published_ts = 0.0
                                parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
                                if parsed_time:
                                    try:
                                        published_ts = calendar.timegm(parsed_time)
                                    except Exception:
                                        published_ts = 0.0

                                published_str = entry.get("published", "")
                                if published_ts > 0:
                                    gmt7_struct = time.gmtime(published_ts + 7 * 3600)
                                    published_str = time.strftime("%H:%M:%S %d/%m/%Y (GMT+7)", gmt7_struct)

                                posts.append(PostItem(
                                    post_id=post_id,
                                    author=username,
                                    content=clean_summary,
                                    url=link,
                                    published_at=published_str,
                                    published_timestamp=published_ts,
                                    is_retweet=False,
                                    media_urls=media_urls
                                ))
                            return posts, None
            except Exception as e:
                errors.append(f"{instance}: {str(e)}")

        return [], f"Không thể lấy bài đăng công khai từ @{username}."

