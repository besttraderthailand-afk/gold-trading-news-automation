"""
Gold Trading News Automation - Main Entry Point
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure project root is in path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from loguru import logger
from config.settings import get_settings
from src.calendar_scanner import CalendarScanner
from src.news_scanner import NewsScanner
from src.impact_analyzer import ImpactAnalyzer
from src.telegram_bot import TelegramReporter
from src.scheduler import AutomationScheduler


def setup_logging():
    settings = get_settings()
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
    )
    logger.add(
        "logs/automation_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="14 days",
        level="DEBUG",
    )


async def run_daily_once():
    """รัน Daily Report ครั้งเดียว (สำหรับทดสอบ)"""
    logger.info("=== Running Daily Report (once) ===")
    calendar = CalendarScanner()
    news_scanner = NewsScanner()
    telegram = TelegramReporter()

    events = await calendar.fetch_events()
    news = await news_scanner.scan(hours_back=12)
    high_news = news_scanner.get_high_impact_only(news)

    logger.info(f"Found {len(events)} calendar events, {len(high_news)} high impact news")

    success = await telegram.send_daily_report(
        events=events,
        news=high_news,
        dxy_status="ทรงตัว",
        dxy_value="N/A",
    )
    if success:
        logger.info("✅ Daily Report sent to Telegram")
    else:
        logger.error("❌ Failed to send Daily Report")


async def run_flash_once():
    """รัน Flash News scan ครั้งเดียว"""
    logger.info("=== Running Flash News Scan (once) ===")
    news_scanner = NewsScanner()
    telegram = TelegramReporter()

    news = await news_scanner.scan(hours_back=3)
    high = news_scanner.get_high_impact_only(news)

    logger.info(f"Found {len(high)} high impact flash news")
    for n in high[:3]:
        await telegram.send_flash_alert(n)
        logger.info(f"Sent: {n.title_en[:50]}")


async def run_full_report():
    """สร้างและส่งรายงานฉบับเต็ม"""
    logger.info("=== Generating Full Report ===")
    calendar = CalendarScanner()
    news_scanner = NewsScanner()
    telegram = TelegramReporter()

    events = await calendar.fetch_events()
    news = await news_scanner.scan(hours_back=12)

    success = await telegram.send_full_report(events, news)
    if success:
        logger.info("✅ Full Report sent")
    else:
        logger.error("❌ Full Report failed")


async def run_scheduler():
    """รัน Scheduler แบบต่อเนื่อง"""
    logger.info("=== Starting Automation Scheduler ===")
    scheduler = AutomationScheduler()
    scheduler.start()

    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.stop()
        logger.info("Shutdown complete")


def main():
    parser = argparse.ArgumentParser(
        description="Gold Trading News Automation System"
    )
    parser.add_argument(
        "--mode",
        choices=["daily", "flash", "full", "scheduler"],
        default="daily",
        help="Mode: daily (once), flash (once), full report, or scheduler (continuous)",
    )
    args = parser.parse_args()

    setup_logging()
    logger.info(f"Starting in mode: {args.mode}")

    if args.mode == "daily":
        asyncio.run(run_daily_once())
    elif args.mode == "flash":
        asyncio.run(run_flash_once())
    elif args.mode == "full":
        asyncio.run(run_full_report())
    elif args.mode == "scheduler":
        asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
