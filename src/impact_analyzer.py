"""
ขั้นตอนที่ 3: Multi-Asset Impact Matrix
จับคู่ข่าว/ตัวเลขเศรษฐกิจกับผลกระทบต่อทองคำ (XAUUSD)
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger

from src.calendar_scanner import EconomicEvent
from src.news_scanner import FlashNews
from config.settings import get_settings


@dataclass
class ImpactItem:
    title: str
    level: str  # high / medium / low
    analysis: str
    source_type: str  # calendar / news
    surprise_delta: Optional[float] = None
    time_str: str = ""
    sentiment_score: float = 0.0
    sentiment_label: str = "neutral"
    sentiment_emoji: str = "⚪"
    gold_bias: str = "neutral"


class ImpactAnalyzer:
    """
    วิเคราะห์และจัดกลุ่มผลกระทบตามสเปค:
    🔥 High Impact
    ⚠️ Medium Impact
    💡 Low Impact
    """

    def __init__(self):
        self.settings = get_settings()

    def analyze(
        self,
        events: List[EconomicEvent],
        news: List[FlashNews],
        dxy_status: str = "ทรงตัว",
        dxy_value: str = "N/A",
    ) -> Dict[str, Any]:
        """
        สร้าง Impact Matrix ครบชุด
        """
        high: List[ImpactItem] = []
        medium: List[ImpactItem] = []
        low: List[ImpactItem] = []

        # จาก Economic Calendar
        for ev in events:
            item = self._event_to_impact(ev)
            if item.level == "high":
                high.append(item)
            elif item.level == "medium":
                medium.append(item)
            else:
                low.append(item)

        # จาก Flash News
        for n in news:
            item = self._news_to_impact(n)
            if item.level == "high":
                high.append(item)
            elif item.level == "medium":
                medium.append(item)
            else:
                low.append(item)

        strategy = self._generate_daily_strategy(high, medium, events)

        return {
            "dxy_status": dxy_status,
            "dxy_value": dxy_value,
            "high_impact": high,
            "medium_impact": medium,
            "low_impact": low,
            "strategy": strategy,
            "focus_asset": "ทองคำ (XAUUSD)",
        }

    def _event_to_impact(self, ev: EconomicEvent) -> ImpactItem:
        level = "high" if ev.importance == "high" else "medium"
        if ev.importance == "low":
            level = "low"

        # Upgrade to high if large surprise
        if ev.surprise_delta is not None and abs(ev.surprise_delta) >= self.settings.high_surprise_delta:
            level = "high"

        time_str = ev.time.strftime("%H:%M") if ev.time else ""
        analysis = ev.impact_on_gold or "ติดตามเพิ่มเติม"

        return ImpactItem(
            title=f"{ev.event} ({ev.country})",
            level=level,
            analysis=analysis,
            source_type="calendar",
            surprise_delta=ev.surprise_delta,
            time_str=time_str,
        )

    def _news_to_impact(self, news: FlashNews) -> ImpactItem:
        # Prefer sentiment-based analysis when available
        if news.sentiment and news.sentiment.confidence >= 0.4:
            analysis = f"{news.sentiment.emoji} {news.sentiment.summary_th}"
        else:
            analysis = self._build_news_analysis(news)

        emoji = "⚪"
        if news.sentiment:
            emoji = news.sentiment.emoji

        return ImpactItem(
            title=news.title_th or news.title_en,
            level=news.impact_level,
            analysis=analysis,
            source_type="news",
            time_str=news.time.strftime("%H:%M") if news.time else "",
            sentiment_score=news.sentiment_score,
            sentiment_label=news.sentiment_label,
            sentiment_emoji=emoji,
            gold_bias=news.gold_bias,
        )

    def _build_news_analysis(self, news: FlashNews) -> str:
        cat = news.category
        title = news.title_en.upper()

        if cat == "monetary":
            if any(w in title for w in ["CUT", "DOVISH", "LOWER"]):
                return "แนวโน้มบวกต่อทองคำ (นโยบายผ่อนคลาย → DXY อ่อน)"
            if any(w in title for w in ["HIKE", "HAWKISH", "HIGHER"]):
                return "แนวโน้มลบต่อทองคำ (นโยบายตึงตัว → DXY แข็ง)"
            return "ติดตามถ้อยแถลง Fed/CB อย่างใกล้ชิด"

        if cat == "inflation":
            if "HIGHER" in title or "SURGE" in title or "HOT" in title:
                return "เงินเฟ้อสูงกว่าคาด → กดดันทองคำระยะสั้น"
            if "COOL" in title or "LOWER" in title or "SLOW" in title:
                return "เงินเฟ้อชะลอ → บวกต่อทองคำ"
            return "รอตัวเลขจริงเพื่อประเมิน Surprise Delta"

        if cat == "geopolitics":
            return "ความเสี่ยงภูมิรัฐศาสตร์ → ทองคำมีแนวโน้มเป็น Safe-haven"

        if cat == "energy":
            return "ผลกระทบทางอ้อมผ่านเงินเฟ้อและ Risk Sentiment"

        return "ผลกระทบจำกัดต่อทองคำในระยะสั้น"

    def _generate_daily_strategy(
        self,
        high: List[ImpactItem],
        medium: List[ImpactItem],
        events: List[EconomicEvent],
    ) -> str:
        if not high and not medium:
            return "วันนี้ไม่มีข่าว High Impact ชัดเจน – เทรดตามแนวโน้มหลัก บริหารความเสี่ยงปกติ"

        high_count = len(high)
        has_cpi = any("CPI" in i.title.upper() or "PCE" in i.title.upper() for i in high + medium)
        has_fed = any("FED" in i.title.upper() or "FOMC" in i.title.upper() or "RATE" in i.title.upper() for i in high + medium)
        has_geo = any(i.level == "high" and "geo" in (i.analysis.lower() + i.title.lower()) for i in high)

        # Sentiment bias from news
        all_items = high + medium
        bullish = sum(1 for i in all_items if i.gold_bias == "positive")
        bearish = sum(1 for i in all_items if i.gold_bias == "negative")
        avg_score = (
            sum(i.sentiment_score for i in all_items) / len(all_items)
            if all_items else 0.0
        )

        parts = []
        if has_cpi or has_fed:
            parts.append("ระวังความผันผวนสูงช่วงประกาศตัวเลขสำคัญ ลดขนาด Position หรือรอ Confirmation หลังข่าว")
        if has_geo:
            parts.append("ความเสี่ยงภูมิรัฐศาสตร์สูง – ทองคำอาจได้รับแรงซื้อ Safe-haven")
        if high_count >= 2:
            parts.append(f"มีข่าว High Impact {high_count} รายการ – เตรียม Stop Loss ให้กว้างขึ้น")

        # Sentiment-driven guidance
        if avg_score >= 0.35 and bullish > bearish:
            parts.append(f"Sentiment รวมเป็นบวกต่อทองคำ (score {avg_score:+.2f}) – เน้นหาจังหวะ Long")
        elif avg_score <= -0.35 and bearish > bullish:
            parts.append(f"Sentiment รวมเป็นลบต่อทองคำ (score {avg_score:+.2f}) – ระวังแรงขาย / พิจารณาลด Long")
        elif bullish > 0 or bearish > 0:
            parts.append(f"Sentiment ผสม (Bull {bullish} / Bear {bearish}) – รอ confirmation ก่อนเพิ่ม position")

        if not parts:
            parts.append("ติดตามข่าว Medium Impact และบริหารความเสี่ยงตามแผนปกติ")

        return " | ".join(parts)

    def format_full_report(
        self,
        analysis: Dict[str, Any],
        events: List[EconomicEvent],
        date_str: str,
    ) -> str:
        """
        สร้างรายงานฉบับเต็มตาม Template ในสเปค (ส่วนที่ 4)
        """
        lines = [
            "# 📊 รายงานวิเคราะห์ภาวะตลาดและผลกระทบการลงทุน",
            f"**🎯 สินทรัพย์หลักที่โฟกัส:** {analysis['focus_asset']}",
            f"**📅 ประจำวันที่:** {date_str}",
            "",
            "### 🗓️ ปฏิทินตัวเลขเศรษฐกิจและการวิเคราะห์ (Economic Indicators)",
            "",
            "| เวลา | ตัวเลขเศรษฐกิจ / เหตุการณ์ | คาดการณ์ | ประกาศจริง | Surprise Delta | ผลกระทบต่อ ทองคำ |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        for ev in events:
            time_str = ev.time.strftime("%H:%M") if ev.time else "-"
            actual = f"**{ev.actual}**" if ev.actual else "-"
            forecast = ev.forecast or "-"
            delta = f"{ev.surprise_delta:+.2f}" if ev.surprise_delta is not None else "-"
            if ev.surprise_delta and abs(ev.surprise_delta) >= 0.2:
                delta += " 🔴"
            impact = ev.impact_on_gold or "-"
            lines.append(f"| {time_str} | {ev.event} | {forecast} | {actual} | {delta} | {impact} |")

        lines.extend([
            "",
            "### 🔥 การจัดกลุ่มข่าวตามระดับผลกระทบ (Impact Categories)",
            "",
        ])

        if analysis["high_impact"]:
            lines.append("* **🔴 High Impact:**")
            for item in analysis["high_impact"]:
                sent = f" {item.sentiment_emoji}" if item.sentiment_emoji != "⚪" else ""
                lines.append(f"  - {item.title}{sent} → {item.analysis}")
        else:
            lines.append("* **🔴 High Impact:** ไม่มีในขณะนี้")

        lines.append("")
        if analysis["medium_impact"]:
            lines.append("* **🟡 Medium Impact:**")
            for item in analysis["medium_impact"][:5]:
                sent = f" {item.sentiment_emoji}" if item.sentiment_emoji != "⚪" else ""
                lines.append(f"  - {item.title}{sent} → {item.analysis}")
        else:
            lines.append("* **🟡 Medium Impact:** ไม่มีในขณะนี้")

        lines.append("")
        lines.append("* **🟢 Low Impact:** ข่าวทั่วไปที่ไม่มีผลอย่างมีนัยสำคัญต่อทองคำ")

        # Sentiment Summary section
        all_news_items = analysis["high_impact"] + analysis["medium_impact"]
        news_with_sent = [i for i in all_news_items if i.source_type == "news" and i.sentiment_score != 0]
        if news_with_sent:
            avg = sum(i.sentiment_score for i in news_with_sent) / len(news_with_sent)
            bull = sum(1 for i in news_with_sent if i.gold_bias == "positive")
            bear = sum(1 for i in news_with_sent if i.gold_bias == "negative")
            lines.extend([
                "",
                "### 📈 สรุป Sentiment ต่อทองคำ (XAUUSD)",
                f"- คะแนนเฉลี่ย: **{avg:+.2f}** (−1 ลบสุด → +1 บวกสุด)",
                f"- ข่าว Bullish: {bull} | ข่าว Bearish: {bear}",
            ])

        lines.append("")
        lines.append("---")
        lines.append("⚠️ *การวิเคราะห์จัดทำขึ้นเพื่อการให้ข้อมูลเท่านั้น ไม่ถือเป็นคำแนะนำทางการเงิน (Not Financial Advice)*")

        return "\n".join(lines)
