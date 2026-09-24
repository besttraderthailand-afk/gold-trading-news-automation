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









def test_simple_th_title_preserves_proper_nouns():
    scanner = NewsScanner.__new__(NewsScanner)
    title = "Surging Treasury yields pose a brand new problem for Kevin Warsh and the Fed"
    out = scanner._simple_th_title(title)
    assert "สงคราม" not in out
    assert "Warsh" in out
    assert "Fed" in out


def test_flash_alert_template_matches_skill_structure():
    import asyncio
    from types import SimpleNamespace
    from src.telegram_bot import TelegramReporter
    from src.sentiment import SentimentResult, SentimentLabel

    captured = {}

    class FakeReporter(TelegramReporter):
        async def _send(self, text, parse_mode=None):
            captured["text"] = text
            return True

    news = FlashNews(
        title_th="Kevin Warsh and the Fed",
        title_en="Kevin Warsh and the Fed",
        source="CNBC",
        time=datetime.now(pytz.timezone("Asia/Bangkok")),
        sentiment=SentimentResult(
            label=SentimentLabel.NEUTRAL,
            score=0.0,
            confidence=0.35,
            matched_phrases=["yields"],
            gold_bias="neutral",
            summary_th="ผลกระทบจำกัด",
            summary_en="limited impact",
        ),
    )
    bot = FakeReporter.__new__(FakeReporter)
    bot.tz = pytz.timezone("Asia/Bangkok")
    bot.analyzer = SimpleNamespace(_build_news_analysis=lambda n: "fallback")
    asyncio.run(FakeReporter.send_flash_alert(bot, news, analysis_text="ผลกระทบต่อทองคำยังจำกัด"))
    text = captured["text"]
    assert "หัวข้อข่าว" in text
    assert "สำนักข่าว" in text
    assert "บทวิเคราะห์ต่อทองคำ XAUUSD" in text
    assert "Kevin Warsh" in text
    assert "สงคราม" not in text
    assert "score " not in text
    assert "conf " not in text


def test_sent_flash_store_persists(tmp_path):
    from src.sent_store import SentFlashStore
    store_path = tmp_path / "sent_flash.json"
    s1 = SentFlashStore(store_path)
    assert s1.add("abc123") is True
    assert s1.add("abc123") is False
    s2 = SentFlashStore(store_path)
    assert s2.has("abc123") is True
    assert s2.add("abc123") is False


def test_flash_fingerprint_same_title_source():
    from datetime import datetime
    import pytz
    from src.news_scanner import FlashNews
    n1 = FlashNews(
        title_th="t",
        title_en="Kevin Warsh and the Fed",
        source="CNBC Top News",
        time=datetime.now(pytz.UTC),
    )
    n2 = FlashNews(
        title_th="t2",
        title_en="Kevin Warsh and the Fed",
        source="CNBC Top News",
        time=datetime.now(pytz.UTC),
    )
    assert n1.fingerprint() == n2.fingerprint()
