"""
Scheduler สำหรับ Daily Report + Flash News Monitor
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
            f"Flash check every {self.settings.flash_check_interval_minutes} min"
        )

    def stop(self):
        self.scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
