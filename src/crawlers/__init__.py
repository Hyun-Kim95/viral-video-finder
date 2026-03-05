# crawlers package
from .base import CrawlResult
from .youtube_crawler import YouTubeCrawler
from .instagram_crawler import InstagramCrawler

__all__ = ["CrawlResult", "YouTubeCrawler", "InstagramCrawler"]
