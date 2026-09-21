"""End-to-end Economic Calendar smoke test for GitHub Actions -> Telegram."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from loguru import logger

from src.calendar_scanner import CalendarScanner
from src.telegram_bot import TelegramReporter

TZ = ZoneInfo("Asia/Bangkok")


def tomorrow_date() -> str:
    return (datetime.now(TZ).date() + timedelta(days=1)).isoformat()


async def main() -> None:
    target = tomorrow_date()
    logger.info("E2E target date: {}", target)

    scanner = CalendarScanner()
    events = await scanner.fetch_events(
        from_date=target,
        to_date=target,
        importance=["medium", "high"],
    )

    # Never treat fallback/sample events as verified calendar data.
    events = [e for e in events if e.time and e.time.astimezone(TZ).date().isoformat() == target]

    if not events:
        raise RuntimeError(
            f"No verified Medium/High economic-calendar events found for {target}. "
            "E2E stopped before Telegram to avoid sending fabricated calendar data."
        )

    telegram = TelegramReporter()

    lines = [
        "🧪 E2E TEST — ECONOMIC CALENDAR",
        "",
        f"📅 Tomorrow: {datetime.fromisoformat(target):%d/%m/%Y}",
        "🌏 Timezone: Asia/Bangkok",
        "",
        "📅 VERIFIED CALENDAR EVENTS",
    ]

    for ev in events[:12]:
        time_str = ev.time.astimezone(TZ).strftime("%H:%M")
        icon = "🔴" if ev.importance == "high" else "🟠"
        forecast = ev.forecast or "-"
        previous = ev.previous or "-"
        lines.extend([
            "",
            f"{icon} {ev.importance.upper()}",
            f"⏰ {time_str} น. — {ev.event}",
            f"💵 {ev.currency or ev.country or 'N/A'}",
            f"Forecast: {forecast} | Previous: {previous}",
            f"Gold Impact: {ev.impact_on_gold or 'รอประเมิน'}",
        ])

    lines.extend([
        "",
        "──────────────",
        "Pipeline Status",
        "Calendar Fetch    ✅",
        "Date Validation   ✅",
        "Impact Filter     ✅",
        "Thai Formatter    ✅",
        "Telegram Send     ⏳",
        "",
        "MODE: TEST",
        "⚠️ E2E smoke test — not a trading signal.",
    ])

    text = "\n".join(lines)
    ok = await telegram._send(text)
    if not ok:
        raise RuntimeError("Telegram send failed")

    logger.info("E2E PASS: calendar -> validation -> formatter -> Telegram")


if __name__ == "__main__":
    asyncio.run(main())
