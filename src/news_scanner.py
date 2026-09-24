"""
ขั้นตอนที่ 2: Real-time Breaking News / Flash News Scan
สแกนพาดหัวข่าวจากแหล่งที่น่าเชื่อถือตาม Keyword Mapping
"""
from __future__ import annotations

import httpx
import feedparser
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Set
from dataclasses import dataclass, field
from loguru import logger
import pytz
import hashlib
import re

from config.settings import get_settings
from src.sentiment import SentimentResult, analyze_sentiment, SentimentLabel


@dataclass
class FlashNews:
    title_th: str
    title_en: str
    source: str
    time: datetime
    url: str = ""
    category: str = ""  # monetary / inflation / geopolitics / energy / crypto
    impact_level: str = "medium"  # high / medium / low
    keywords_matched: List[str] = field(default_factory=list)
    summary: str = ""
    actual: Optional[str] = None
    forecast: Optional[str] = None
    # Sentiment Analysis fields
    sentiment: Optional[SentimentResult] = None
    sentiment_score: float = 0.0
    sentiment_label: str = "neutral"
    gold_bias: str = "neutral"  # positive / negative / neutral

    def fingerprint(self) -> str:
        """สำหรับ Deduplication"""
        key = f"{self.title_en.lower()}|{self.source}"
        return hashlib.md5(key.encode()).hexdigest()

    def apply_sentiment(self) -> None:
        """รัน sentiment analysis และเก็บผลลัพธ์"""
        result = analyze_sentiment(self.title_en, category=self.category)
        self.sentiment = result
        self.sentiment_score = result.score
        self.sentiment_label = result.label.value
        self.gold_bias = result.gold_bias


class NewsScanner:
    """
    Scanner สำหรับ Flash News / Breaking News
    ใช้ RSS feeds + NewsAPI (ถ้ามี key) + keyword matching
    """

    # Reliable free RSS sources
    RSS_FEEDS = [
        ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
        ("Reuters World", "https://feeds.reuters.com/Reuters/worldNews"),
        ("CNBC Top News", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
        ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
        ("Fed News", "https://www.federalreserve.gov/feeds/press_all.xml"),
        ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    ]

    def __init__(self):
        self.settings = get_settings()
        self.tz = pytz.timezone(self.settings.timezone)
        self.seen_fingerprints: Set[str] = set()
        self._load_keyword_map()

    def _load_keyword_map(self):
        self.keyword_map = {
            "monetary": self.settings.monetary_policy_keywords,
            "inflation": self.settings.inflation_jobs_keywords,
            "geopolitics": self.settings.geopolitics_keywords,
            "energy": self.settings.energy_keywords,
            "crypto": self.settings.crypto_tech_keywords,
        }

    async def scan(self, hours_back: int = 6) -> List[FlashNews]:
        """สแกนข่าวด่วนล่าสุด"""
        all_news: List[FlashNews] = []

        # 1. RSS Feeds
        rss_news = await self._scan_rss(hours_back)
        all_news.extend(rss_news)

        # 2. NewsAPI (ถ้ามี key)
        if self.settings.news_api_key:
            newsapi = await self._scan_newsapi(hours_back)
            all_news.extend(newsapi)

        # 3. Finnhub (ถ้ามี key)
        if self.settings.finnhub_api_key:
            finnhub = await self._scan_finnhub()
            all_news.extend(finnhub)

        # Deduplication
        unique = self._deduplicate(all_news)

        # Classify impact + run Sentiment Analysis
        for news in unique:
            news.category = self._detect_category(news)
            news.impact_level = self._classify_impact(news)
            news.apply_sentiment()  # ← Sentiment Analysis

        # Sort by impact → sentiment strength → time
        unique.sort(key=lambda x: (
            0 if x.impact_level == "high" else 1 if x.impact_level == "medium" else 2,
            -abs(x.sentiment_score),  # stronger sentiment first
            -(x.time.timestamp() if x.time else 0)
        ))

        logger.info(
            f"Scanned {len(unique)} unique flash news | "
            f"Bullish: {sum(1 for n in unique if n.gold_bias == 'positive')} | "
            f"Bearish: {sum(1 for n in unique if n.gold_bias == 'negative')}"
        )
        return unique

    async def _scan_rss(self, hours_back: int) -> List[FlashNews]:
        results = []
        cutoff = datetime.now(self.tz) - timedelta(hours=hours_back)

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            for source_name, url in self.RSS_FEEDS:
                try:
                    resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code != 200:
                        continue
                    feed = feedparser.parse(resp.text)
                    for entry in feed.entries[:15]:
                        title = entry.get("title", "")
                        if not self._is_relevant(title):
                            continue

                        published = self._parse_rss_time(entry)
                        if published and published < cutoff:
                            continue

                        news = FlashNews(
                            title_th=self._simple_th_title(title),
                            title_en=title,
                            source=source_name,
                            time=published or datetime.now(self.tz),
                            url=entry.get("link", ""),
                            keywords_matched=self._extract_keywords(title),
                        )
                        results.append(news)
                except Exception as e:
                    logger.debug(f"RSS {source_name} error: {e}")
        return results

    async def _scan_newsapi(self, hours_back: int) -> List[FlashNews]:
        results = []
        try:
            query = "OR".join([
                "Fed OR FOMC OR CPI OR \"interest rate\" OR Powell",
                "OR \"non-farm\" OR NFP OR OPEC OR sanctions"
            ])
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 20,
                "apiKey": self.settings.news_api_key,
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params)
                data = resp.json()
                for art in data.get("articles", []):
                    title = art.get("title", "")
                    if not self._is_relevant(title):
                        continue
                    published = datetime.fromisoformat(
                        art["publishedAt"].replace("Z", "+00:00")
                    ).astimezone(self.tz)
                    results.append(FlashNews(
                        title_th=self._simple_th_title(title),
                        title_en=title,
                        source=art.get("source", {}).get("name", "NewsAPI"),
                        time=published,
                        url=art.get("url", ""),
                        keywords_matched=self._extract_keywords(title),
                    ))
        except Exception as e:
            logger.debug(f"NewsAPI error: {e}")
        return results

    async def _scan_finnhub(self) -> List[FlashNews]:
        results = []
        try:
            url = "https://finnhub.io/api/v1/news"
            params = {"category": "general", "token": self.settings.finnhub_api_key}
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params)
                data = resp.json()
                for art in data[:20]:
                    title = art.get("headline", "")
                    if not self._is_relevant(title):
                        continue
                    ts = art.get("datetime", 0)
                    published = datetime.fromtimestamp(ts, tz=self.tz) if ts else datetime.now(self.tz)
                    results.append(FlashNews(
                        title_th=self._simple_th_title(title),
                        title_en=title,
                        source=art.get("source", "Finnhub"),
                        time=published,
                        url=art.get("url", ""),
                        keywords_matched=self._extract_keywords(title),
                    ))
        except Exception as e:
            logger.debug(f"Finnhub error: {e}")
        return results

    def _is_relevant(self, title: str) -> bool:
        title_upper = title.upper()
        all_keywords = (
            self.settings.monetary_policy_keywords +
            self.settings.inflation_jobs_keywords +
            self.settings.geopolitics_keywords +
            self.settings.energy_keywords
        )
        return any(kw.upper() in title_upper for kw in all_keywords)

    def _extract_keywords(self, title: str) -> List[str]:
        title_upper = title.upper()
        matched = []
        for cat, kws in self.keyword_map.items():
            for kw in kws:
                if kw.upper() in title_upper:
                    matched.append(kw)
        return list(set(matched))

    def _detect_category(self, news: FlashNews) -> str:
        title = news.title_en.upper()
        for cat, kws in self.keyword_map.items():
            if any(kw.upper() in title for kw in kws):
                return cat
        return "general"

    def _classify_impact(self, news: FlashNews) -> str:
        """
        High Impact ตามสเปค:
        - Fed decision / Powell speech
        - CPI/PCE surprise
        - Geopolitical shocks
        """
        title = news.title_en.upper()
        high_triggers = [
            "FOMC", "FED RATE", "RATE DECISION", "POWELL", "INTEREST RATE DECISION",
            "CPI", "PCE", "NON-FARM", "NFP", "UNEMPLOYMENT",
            "WAR", "ATTACK", "SANCTIONS", "INVASION", "MISSILE",
            "EMERGENCY", "SURPRISE", "UNEXPECTED"
        ]
        if any(t in title for t in high_triggers):
            return "high"
        if news.category in ("monetary", "inflation", "geopolitics"):
            return "medium"
        return "low"

    def _deduplicate(self, news_list: List[FlashNews]) -> List[FlashNews]:
        unique = []
        for n in news_list:
            fp = n.fingerprint()
            if fp not in self.seen_fingerprints:
                self.seen_fingerprints.add(fp)
                unique.append(n)
        # Keep only last 200 fingerprints in memory
        if len(self.seen_fingerprints) > 200:
            self.seen_fingerprints = set(list(self.seen_fingerprints)[-150:])
        return unique

    def _parse_rss_time(self, entry) -> Optional[datetime]:
        try:
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                return datetime(*entry.published_parsed[:6], tzinfo=pytz.UTC).astimezone(self.tz)
            if hasattr(entry, "updated_parsed") and entry.updated_parsed:
                return datetime(*entry.updated_parsed[:6], tzinfo=pytz.UTC).astimezone(self.tz)
        except Exception:
            pass
        return None

    def _simple_th_title(self, en_title: str) -> str:
        """หัวข้อภาษาไทยแบบปลอดภัย (skill.md §1.2)

        ห้ามแปลคำต่อคำแบบ substring — จะเพี้ยนชื่อเฉพาะ เช่น Warsh → สงครามsh
        จนกว่าจะต่อ LLM ขัดเกลา ให้คงหัวข้ออังกฤษไว้ (ข้อความ Flash จะแสดงต้นฉบับชัดเจน)
        """
        return (en_title or "").strip()

    def get_high_impact_only(self, news_list: List[FlashNews]) -> List[FlashNews]:
        return [n for n in news_list if n.impact_level == "high"]
