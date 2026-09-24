"""
Telegram Automation System
3.1 Daily Scheduled Report
3.2 Real-time Flash News Alert
3.3 Pre-release + Economic Data Release
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Any, Optional
from loguru import logger
import pytz
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from config.settings import get_settings
from src.calendar_scanner import EconomicEvent
from src.news_scanner import FlashNews
from src.impact_analyzer import ImpactAnalyzer, ImpactItem


class TelegramReporter:
    def __init__(self):
        self.settings = get_settings()
        self.bot = Bot(token=self.settings.telegram_bot_token)
        self.chat_id = self.settings.telegram_chat_id
        self.tz = pytz.timezone(self.settings.timezone)
        self.analyzer = ImpactAnalyzer()

    async def send_daily_report(
        self,
        events: List[EconomicEvent],
        news: List[FlashNews],
        dxy_status: str = "ทรงตัว",
        dxy_value: str = "N/A",
    ) -> bool:
        """
        3.1 รายงานสรุปประจำวัน 07:00 น.
        โครงสร้างตามสเปคเป๊ะ
        """
        analysis = self.analyzer.analyze(events, news, dxy_status, dxy_value)
        now = datetime.now(self.tz)
        date_str = now.strftime("%d/%m/%Y")

        # Build message ตาม Template
        lines = [
            "📊 *สรุปภาวะตลาดและข่าวสารการลงทุนประจำวัน*",
            f"📅 ประจำวันที่: {date_str} | ⏰ 07:00 น.",
            f"🎯 *สินทรัพย์หลัก:* ทองคำ (XAUUSD)",
            f"📉 *ดัชนีดอลลาร์ (DXY):* {dxy_status} ({dxy_value})",
            "",
            "---",
            "🔴 *ข่าวผลกระทบสูง (High Impact):*",
        ]

        high_items = analysis["high_impact"]
        if high_items:
            for item in high_items[:5]:
                sent = f" {item.sentiment_emoji}" if item.sentiment_emoji and item.sentiment_emoji != "⚪" else ""
                lines.append(f"• {item.title}{sent} - {item.analysis}")
        else:
            lines.append("• ไม่มีข่าว High Impact ในช่วงนี้")

        # Sentiment overview
        news_items = [i for i in (analysis["high_impact"] + analysis["medium_impact"]) if i.source_type == "news"]
        if news_items:
            avg = sum(i.sentiment_score for i in news_items) / len(news_items)
            emoji = "🟢" if avg > 0.2 else "🔴" if avg < -0.2 else "⚪"
            lines.append("")
            lines.append(f"📈 *Sentiment ทองคำ:* {emoji} {avg:+.2f} (Bull {sum(1 for i in news_items if i.gold_bias=='positive')} / Bear {sum(1 for i in news_items if i.gold_bias=='negative')})")

        lines.append("")
        lines.append("🗓️ *ปฏิทินเศรษฐกิจน่าจับตาวันนี้:*")

        today_events = [
            e for e in events
            if e.time and e.time.date() == now.date()
        ]
        if not today_events:
            today_events = events[:5]

        if today_events:
            for ev in today_events[:6]:
                time_str = ev.time.strftime("%H:%M") if ev.time else "--:--"
                forecast = ev.forecast or "-"
                impact = "High" if ev.importance == "high" else "Medium"
                lines.append(f"• {time_str} {ev.event} | คาดการณ์: {forecast} (ผลกระทบ: {impact})")
        else:
            lines.append("• ไม่มีตัวเลขสำคัญวันนี้")

        lines.append("")
        lines.append(f"💡 *กลยุทธ์ประจำวัน:* {analysis['strategy']}")
        lines.append("")
        lines.append("_การวิเคราะห์เพื่อข้อมูลเท่านั้น | Not Financial Advice_")

        text = "\n".join(lines)
        return await self._send(text)

    async def send_flash_alert(
        self,
        news: FlashNews,
        analysis_text: Optional[str] = None,
        actual: Optional[str] = None,
        forecast: Optional[str] = None,
    ) -> bool:
        """
        3.2 ระบบแจ้งเตือนข่าวด่วนฉุกเฉิน
        โครงสร้างตามสเปคเป๊ะ
        """
        time_str = news.time.strftime("%H:%M") if news.time else datetime.now(self.tz).strftime("%H:%M")

        # Prefer sentiment summary when available
        if analysis_text is None:
            if news.sentiment and news.sentiment.confidence >= 0.35:
                analysis_text = f"{news.sentiment.emoji} {news.sentiment.summary_th}"
            else:
                analysis_text = self.analyzer._build_news_analysis(news)

        # โครงสร้างตาม skill.md §3.2 — ไม่โชว์ score/conf ดิบ และไม่รวมหัวข้อไทย+อังกฤษเพี้ยนในบรรทัดเดียว
        lines = [
            "🚨 *[FLASH NEWS] แจ้งเตือนข่าวด่วนส่งผลกระทบสูง*",
            "",
        ]

        title_th = (news.title_th or "").strip()
        title_en = (news.title_en or "").strip()
        if title_th and title_en and title_th.lower() != title_en.lower():
            lines.append(f"📌 *หัวข้อข่าว:* {title_th}")
            lines.append(f"({title_en})")
        else:
            lines.append(f"📌 *หัวข้อข่าว:* {title_en or title_th}")

        lines.append(f"🏛️ *สำนักข่าว:* {news.source} | ⏰ *เวลา:* {time_str}")

        if actual or forecast:
            a = actual or news.actual or "-"
            f = forecast or news.forecast or "-"
            lines.append(f"📊 *ตัวเลขจริง vs คาดการณ์:* Actual: {a} | Forecast: {f}")

        lines.extend([
            "",
            "💡 *บทวิเคราะห์ต่อทองคำ XAUUSD:*",
            analysis_text,
            "",
            "⚠️ *โปรดเพิ่มความระมัดระวังและบริหารความเสี่ยงในพอร์ตการลงทุน*",
            "",
            "_Not Financial Advice_",
        ])

        text = "\n".join(lines)
        return await self._send(text)


    async def send_pre_release_alert(self, event: EconomicEvent) -> bool:
        """แจ้งเตือนก่อนประกาศตัวเลขสำคัญ (pre-event)"""
        time_str = event.time.strftime("%H:%M") if event.time else "--:--"
        importance = "High" if event.importance == "high" else "Medium"
        currency = event.currency or event.country or "-"
        forecast = event.forecast or "ไม่พบข้อมูล"
        previous = event.previous or "ไม่พบข้อมูล"
        prep = event.impact_on_gold or "เตรียมรับความผันผวนช่วงประกาศ ลดขนาด Position หรือรอ Confirmation"

        lines = [
            "⏰ *[PRE-RELEASE] ใกล้ประกาศตัวเลขสำคัญ*",
            "",
            f"📌 *ตัวเลข:* {event.event}",
            f"🏛️ *ประเทศ/สกุลเงิน:* {currency} | ⏰ *เวลาประกาศ:* {time_str}",
            f"🎚️ *ระดับผลกระทบ:* {importance}",
            "",
            "📈 *ข้อมูลก่อนประกาศ:*",
            f"• *คาดการณ์ (Forecast):* {forecast}",
            f"• *ครั้งก่อน (Previous):* {previous}",
            "• *ประกาศจริง (Actual):* รอประกาศ",
            "",
            "💡 *บทวิเคราะห์เตรียมตัวต่อทองคำ XAUUSD:*",
            prep,
            "",
            "⚠️ *โปรดเพิ่มความระมัดระวังก่อนและระหว่างประกาศ*",
            "",
            "_Not Financial Advice_",
        ]
        return await self._send("\n".join(lines))

    async def send_economic_release_alert(self, event: EconomicEvent) -> bool:
        """
        3.1 Economic Data Release — หลังประกาศ Actual
        ตาม skill.md พร้อม Surprise Delta (score)
        """
        time_str = event.time.strftime("%H:%M") if event.time else datetime.now(self.tz).strftime("%H:%M")
        currency = event.currency or event.country or "-"
        source = event.source or "Economic Calendar"
        actual = event.actual or "ไม่พบข้อมูล"
        forecast = event.forecast or "ไม่พบข้อมูล"
        previous = event.previous or "ไม่พบข้อมูล"

        delta = event.calculate_surprise()
        if delta is None:
            surprise_line = "• *Surprise Delta:* ไม่พบข้อมูล"
            score_line = "• *Impact Score:* N/A"
        else:
            unit = f" {event.unit}" if event.unit else ""
            surprise_line = f"• *Surprise Delta:* {delta:+.4g}{unit}"
            # Impact Score: ขนาด surprise เทียบเกณฑ์ (0–100 clip)
            threshold = float(getattr(self.settings, "high_surprise_delta", 0.2) or 0.2)
            raw = abs(delta) / threshold * 50.0
            score = max(0, min(100, round(raw)))
            direction = "สูงกว่าคาด" if delta > 0 else "ต่ำกว่าคาด" if delta < 0 else "ตรงคาด"
            score_line = f"• *Impact Score:* {score}/100 ({direction})"

        analysis = event.impact_on_gold or self.analyzer._event_to_impact(event).analysis

        lines = [
            "📊 *[ECONOMIC DATA RELEASE] ประกาศตัวเลขเศรษฐกิจ*",
            "",
            f"📌 *ตัวเลข:* {event.event}",
            f"🏛️ *ประเทศ/สกุลเงิน:* {currency} | ⏰ *เวลาประกาศ:* {time_str}",
            f"📰 *แหล่งข้อมูล:* {source}",
            "",
            "📈 *ผลการประกาศ:*",
            f"• *ประกาศจริง (Actual):* {actual}",
            f"• *คาดการณ์ (Forecast):* {forecast}",
            f"• *ครั้งก่อน (Previous):* {previous}",
            surprise_line,
            score_line,
            "",
            "💡 *บทวิเคราะห์ต่อทองคำ XAUUSD:*",
            analysis,
            "",
            "_การวิเคราะห์เพื่อข้อมูลเท่านั้น | Not Financial Advice_",
        ]
        return await self._send("\n".join(lines))

    async def send_full_report(
        self,
        events: List[EconomicEvent],
        news: List[FlashNews],
        dxy_status: str = "ทรงตัว",
        dxy_value: str = "N/A",
    ) -> bool:
        """ส่งรายงานฉบับเต็ม (ส่วนที่ 4)"""
        analysis = self.analyzer.analyze(events, news, dxy_status, dxy_value)
        now = datetime.now(self.tz)
        date_str = now.strftime("%d/%m/%Y %H:%M ICT")
        report = self.analyzer.format_full_report(analysis, events, date_str)

        # Telegram มี limit 4096 chars – แบ่งส่งถ้ายาวเกิน
        if len(report) <= 4000:
            return await self._send(report, parse_mode=ParseMode.MARKDOWN)
        else:
            # ส่งเป็นส่วนๆ
            chunks = [report[i:i+3900] for i in range(0, len(report), 3900)]
            success = True
            for chunk in chunks:
                ok = await self._send(chunk, parse_mode=ParseMode.MARKDOWN)
                if not ok:
                    success = False
            return success

    async def _send(self, text: str, parse_mode: str = ParseMode.MARKDOWN) -> bool:
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=True,
            )
            logger.info("Telegram message sent successfully")
            return True
        except TelegramError as e:
            logger.error(f"Telegram send failed: {e}")
            # Fallback: try without parse_mode
            try:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=text.replace("*", "").replace("_", ""),
                    disable_web_page_preview=True,
                )
                return True
            except Exception as e2:
                logger.error(f"Telegram fallback also failed: {e2}")
                return False
        except Exception as e:
            logger.error(f"Unexpected Telegram error: {e}")
            return False
