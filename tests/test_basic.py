"""
Basic unit tests
"""
import pytest
from datetime import datetime
import pytz

from src.calendar_scanner import EconomicEvent, CalendarScanner
from src.news_scanner import FlashNews, NewsScanner
from src.impact_analyzer import ImpactAnalyzer


def test_surprise_delta_calculation():
    ev = EconomicEvent(
        event="US Core CPI (MoM)",
        time=datetime.now(pytz.UTC),
        timezone="Asia/Bangkok",
        actual="0.5%",
        forecast="0.3%",
        previous="0.2%",
        importance="high",
        country="US",
    )
    delta = ev.calculate_surprise()
    assert delta == pytest.approx(0.2)
    assert ev.surprise_delta == 0.2


def test_impact_assessment_inflation():
    scanner = CalendarScanner()
    ev = EconomicEvent(
        event="US Core CPI (MoM)",
        time=datetime.now(pytz.UTC),
        timezone="Asia/Bangkok",
        actual="0.5%",
        forecast="0.3%",
        previous="0.2%",
        importance="high",
        country="US",
    )
    ev.calculate_surprise()
    impact = scanner._assess_gold_impact(ev)
    assert "ลบ" in impact or "negative" in impact.lower() or "🔴" in impact


def test_news_fingerprint_dedup():
    n1 = FlashNews(
        title_th="ทดสอบ",
        title_en="Fed holds rates",
        source="Reuters",
        time=datetime.now(pytz.UTC),
    )
    n2 = FlashNews(
        title_th="ทดสอบ",
        title_en="Fed holds rates",
        source="Reuters",
        time=datetime.now(pytz.UTC),
    )
    assert n1.fingerprint() == n2.fingerprint()


def test_impact_analyzer_strategy():
    analyzer = ImpactAnalyzer()
    result = analyzer.analyze([], [])
    assert "strategy" in result
    assert result["focus_asset"] == "ทองคำ (XAUUSD)"


def test_sentiment_rate_cut_bullish():
    from src.sentiment import analyze_sentiment, SentimentLabel
    result = analyze_sentiment("Fed cuts rates by 25bps in dovish pivot")
    assert result.score > 0.3
    assert result.gold_bias == "positive"
    assert result.label in (SentimentLabel.BULLISH, SentimentLabel.VERY_BULLISH)


def test_sentiment_rate_hike_bearish():
    from src.sentiment import analyze_sentiment, SentimentLabel
    result = analyze_sentiment("Fed hikes rates 50bps in hawkish surprise")
    assert result.score < -0.3
    assert result.gold_bias == "negative"
    assert result.label in (SentimentLabel.BEARISH, SentimentLabel.VERY_BEARISH)


def test_sentiment_geopolitics_bullish():
    from src.sentiment import analyze_sentiment
    result = analyze_sentiment(
        "Middle East conflict escalates, safe-haven demand rises",
        category="geopolitics",
    )
    assert result.score > 0.2
    assert result.gold_bias == "positive"


def test_sentiment_hot_cpi_bearish():
    from src.sentiment import analyze_sentiment
    result = analyze_sentiment("US CPI surges above expectations, sticky inflation")
    assert result.score < -0.2
    assert result.gold_bias == "negative"
