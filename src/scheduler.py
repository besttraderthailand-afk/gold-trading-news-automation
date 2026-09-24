"""
Scheduler สำหรับ Daily Report + Flash News + Economic Release Monitor
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
import pytz

from config.settings import get_settings
from src.calendar_scanner import CalendarScanner
from src.news_scanner import NewsScanner
from src.telegram_bot import TelegramReporter
from src.sent_store import SentFlashStore


class AutomationScheduler:
    def __init__(self):
        self.settings = get_settings()
        self.tz = pytz.timezone(self.settings.timezone)
        self.scheduler = AsyncIOScheduler(timezone=self.tz)
        self.calendar = CalendarScanner()
        self.news = NewsScanner()
        self.telegram = TelegramReporter()
        self._sent_store = SentFlashStore()
        self._seeded_existing = False

    async def run_daily_report(self):
        """รันรายงานประจำวัน 07:00 น."""
        logger.info("Starting Daily Report job...")
        try:
            events = await self.calendar.fetch_events()
            news = await self.news.scan(hours_back=12)
            high_news = self.news.get_high_impact_only(news)

            # DXY placeholder – สามารถต่อ API จริงได้
            dxy_status = "ทรงตัว"
            dxy_value = "N/A"

            success = await self.telegram.send_daily_report(
                events=events,
                news=high_news,
                dxy_status=dxy_status,
                dxy_value=dxy_value,
            )
            if success:
                logger.info("Daily Report sent successfully")
            else:
                logger.error("Daily Report failed to send")
        except Exception as e:
            logger.exception(f"Daily Report error: {e}")

    async def run_flash_monitor(self):
        """ตรวจสอบ Flash News ทุก X นาที"""
        logger.debug("Running Flash News check...")
        try:
            news_list = await self.news.scan(hours_back=1)
            high_news = self.news.get_high_impact_only(news_list)

            # ครั้งแรกหลังสตาร์ทเมื่อ store ว่าง: จำข่าวในหน้าต่างปัจจุบันโดยไม่ส่ง
            # ป้องกันยิงซ้ำหลังรีสตาร์ท/อัปเดต
            if not self._seeded_existing and len(self._sent_store.known()) == 0 and high_news:
                for news in high_news:
                    self._sent_store.add(news.fingerprint())
                self._seeded_existing = True
                logger.info(
                    f"Seeded {len(high_news)} existing flash items into sent store (no send)"
                )
                return

            self._seeded_existing = True

            for news in high_news:
                fp = news.fingerprint()
                # Claim on disk first so restart / dual process won't re-send
                if not self._sent_store.add(fp):
                    continue

                ok = await self.telegram.send_flash_alert(news)
                if ok is False:
                    logger.error(
                        f"Flash alert failed (kept in sent store to avoid spam): {news.title_en[:60]}"
                    )
                else:
                    logger.info(f"Flash alert sent: {news.title_en[:60]}")

        except Exception as e:
            logger.exception(f"Flash monitor error: {e}")


    def _event_key(self, event, phase: str) -> str:
        """Stable id for pre/post alerts."""
        import hashlib
        t = event.time.isoformat() if event.time else ""
        eid = getattr(event, "event_id", "") or ""
        raw = f"{phase}|{eid}|{event.event}|{t}|{event.country}|{event.currency}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _has_actual(self, event) -> bool:
        a = (event.actual or "").strip()
        return a not in ("", "-", "—", "N/A", "None", "n/a")

    async def run_calendar_monitor(self):
        """
        ตรวจปฏิทินเศรษฐกิจ:
        - ก่อนประกาศ ~ pre_release_alert_minutes (medium/high ที่ยังไม่มี Actual)
        - หลังประกาศทันทีเมื่อมี Actual (Economic Data Release + Surprise/Score)
        """
        logger.debug("Running calendar release monitor...")
        try:
            now = datetime.now(self.tz)
            events = await self.calendar.fetch_events()
            events = self.calendar.filter_medium_high(events)
            pre_mins = int(getattr(self.settings, "pre_release_alert_minutes", 30) or 30)

            for ev in events:
                if not ev.time:
                    continue
                # normalize tz
                et = ev.time
                if et.tzinfo is None:
                    et = self.tz.localize(et)
                else:
                    et = et.astimezone(self.tz)

                minutes_to = (et - now).total_seconds() / 60.0

                # Pre-release: within window, not yet released
                if (not self._has_actual(ev)) and 0 < minutes_to <= pre_mins:
                    key = self._event_key(ev, "pre")
                    if not self._sent_store.add(key):
                        continue
                    ok = await self.telegram.send_pre_release_alert(ev)
                    if ok is False:
                        logger.error(f"Pre-release alert failed: {ev.event}")
                    else:
                        logger.info(f"Pre-release alert sent: {ev.event} in {minutes_to:.0f}m")

                # Post-release: has Actual, event time not too far in future, within last 6h
                if self._has_actual(ev) and minutes_to <= 5:
                    age_min = (now - et).total_seconds() / 60.0
                    if age_min > 360:  # older than 6h — skip
                        continue
                    key = self._event_key(ev, "post")
                    if not self._sent_store.add(key):
                        continue
                    # refresh gold impact with surprise
                    ev.calculate_surprise()
                    if hasattr(self.calendar, "_assess_gold_impact"):
                        ev.impact_on_gold = self.calendar._assess_gold_impact(ev)
                    ok = await self.telegram.send_economic_release_alert(ev)
                    if ok is False:
                        logger.error(f"Economic release alert failed: {ev.event}")
                    else:
                        logger.info(f"Economic release alert sent: {ev.event}")

        except Exception as e:
            logger.exception(f"Calendar monitor error: {e}")

    def start(self):
        """เริ่ม Scheduler"""
        # Daily Report ทุกวัน 07:00 น. เวลาไทย
        self.scheduler.add_job(
            self.run_daily_report,
            trigger=CronTrigger(
                hour=self.settings.daily_report_hour,
                minute=self.settings.daily_report_minute,
                timezone=self.tz,
            ),
            id="daily_report",
            name="Daily Gold Trading Report",
            replace_existing=True,
        )


        # Economic calendar: pre-release + post Actual
        self.scheduler.add_job(
            self.run_calendar_monitor,
            trigger=IntervalTrigger(
                minutes=getattr(self.settings, "calendar_check_interval_minutes", 2),
            ),
            id="calendar_monitor",
            name="Economic Calendar Release Monitor",
            replace_existing=True,
        )

        # Flash News Monitor
        self.scheduler.add_job(
            self.run_flash_monitor,
            trigger=IntervalTrigger(
                minutes=self.settings.flash_check_interval_minutes,
            ),
            id="flash_monitor",
            name="Flash News Monitor",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info(
            f"Scheduler started | Daily Report @ {self.settings.daily_report_hour:02d}:{self.settings.daily_report_minute:02d} ICT | "
            f"Flash check every {self.settings.flash_check_interval_minutes} min | "
            f"Calendar every {getattr(self.settings, 'calendar_check_interval_minutes', 2)} min"
        )

    def stop(self):
        self.scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
