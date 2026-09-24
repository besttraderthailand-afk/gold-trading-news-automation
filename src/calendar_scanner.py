"""
ขั้นตอนที่ 1: Economic Calendar Scan
ดึงข้อมูลปฏิทินเศรษฐกิจ Medium (2 ดาว) และ High (3 ดาว)
"""
from __future__ import annotations

import httpx
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from loguru import logger
import pytz

from config.settings import get_settings


@dataclass
class EconomicEvent:
    event: str
    time: datetime
    timezone: str
    actual: Optional[str] = None
    forecast: Optional[str] = None
    previous: Optional[str] = None
    importance: str = "medium"  # low / medium / high
    country: str = ""
    currency: str = ""
    unit: str = ""
    surprise_delta: Optional[float] = None
    impact_on_gold: str = ""
    source: str = ""
    event_id: str = ""

    def calculate_surprise(self) -> Optional[float]:
        """Surprise Delta = Actual - Forecast"""
        if self.actual is None or self.forecast is None:
            return None
        try:
            def clean(val: str):
                v = str(val).replace("%", "").replace(",", "").strip()
                if v in ("", "-", "—", "N/A", "None"):
                    return None
                return float(v)

            a = clean(self.actual)
            f = clean(self.forecast)
            if a is None or f is None:
                return None
            self.surprise_delta = round(a - f, 4)
            return self.surprise_delta
        except Exception:
            return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event": self.event,
            "time": self.time.isoformat() if self.time else None,
            "timezone": self.timezone,
            "actual": self.actual,
            "forecast": self.forecast,
            "previous": self.previous,
            "importance": self.importance,
            "country": self.country,
            "currency": self.currency,
            "surprise_delta": self.surprise_delta,
            "impact_on_gold": self.impact_on_gold,
            "source": self.source,
        }


class CalendarScanner:
    """
    Scanner สำหรับ Economic Calendar

    Primary: biquote.io
      - สำคัญ: API รับ importance ได้ทีละค่า (medium หรือ high)
        ห้ามส่ง importance=medium,high จะได้ HTTP 400
    Secondary: Forex Factory weekly JSON (ข้อมูลจริง ไม่ใช่ sample)
    """

    BIQUOTE_URL = "https://biquote.io/api/calendar"
    FF_WEEKLY_URLS = (
        "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
        "https://cdn-nfs.faireconomy.media/ff_calendar_thisweek.json",
    )

    FF_CURRENCY_TO_COUNTRY = {
        "USD": "US",
        "EUR": "EU",
        "GBP": "GB",
        "JPY": "JP",
        "CNY": "CN",
        "AUD": "AU",
        "CAD": "CA",
        "NZD": "NZ",
        "CHF": "CH",
    }

    def __init__(self):
        self.settings = get_settings()
        self.tz = pytz.timezone(self.settings.timezone)

    async def fetch_events(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        importance: List[str] = None,
        countries: List[str] = None,
    ) -> List[EconomicEvent]:
        if importance is None:
            importance = ["medium", "high"]
        if countries is None:
            countries = list(getattr(self.settings, "focus_countries", ["US", "EU", "GB", "JP", "CN", "AU", "CA"]))

        if from_date is None:
            from_date = datetime.now(self.tz).strftime("%Y-%m-%d")
        if to_date is None:
            to_date = (datetime.now(self.tz) + timedelta(days=1)).strftime("%Y-%m-%d")

        wanted = []
        for raw in importance:
            v = str(raw).strip().lower()
            if v in ("medium", "high") and v not in wanted:
                wanted.append(v)
        if not wanted:
            wanted = ["medium", "high"]

        events: List[EconomicEvent] = []
        try:
            events = await self._fetch_biquote(from_date, to_date, wanted, countries)
            if events:
                logger.info(f"Fetched {len(events)} economic events from biquote")
            else:
                logger.warning("biquote returned 0 events; trying Forex Factory weekly JSON")
                events = await self._fetch_forexfactory(from_date, to_date, wanted, countries)
        except Exception as e:
            logger.warning(f"biquote API failed: {e}. Trying Forex Factory weekly JSON.")
            try:
                events = await self._fetch_forexfactory(from_date, to_date, wanted, countries)
            except Exception as e2:
                logger.error(
                    f"All calendar sources failed (biquote + Forex Factory): {e2}. "
                    "Returning empty list — will NOT send fabricated sample calendar data."
                )
                events = []

        for ev in events:
            ev.calculate_surprise()
            ev.impact_on_gold = self._assess_gold_impact(ev)

        return sorted(events, key=lambda x: x.time or datetime.min.replace(tzinfo=self.tz))

    async def _fetch_biquote(
        self,
        from_date: str,
        to_date: str,
        importance_levels: List[str],
        countries: List[str],
    ) -> List[EconomicEvent]:
        merged: Dict[str, EconomicEvent] = {}
        countries_param = ",".join(countries)
        headers = {"User-Agent": "gold-trading-news-bot/1.1", "Accept": "application/json"}

        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            for level in importance_levels:
                # IMPORTANT: one importance value per request — comma lists return HTTP 400
                params = {
                    "from": from_date,
                    "to": to_date,
                    "importance": level,
                    "countries": countries_param,
                }
                resp = await client.get(self.BIQUOTE_URL, params=params)
                if resp.status_code >= 400:
                    logger.warning(
                        f"biquote HTTP {resp.status_code} for importance={level}: {resp.text[:200]}"
                    )
                    # retry without countries filter
                    params.pop("countries", None)
                    resp = await client.get(self.BIQUOTE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
                items = data if isinstance(data, list) else data.get("data", [])
                for item in items:
                    event = self._parse_biquote_event(item)
                    if not event:
                        continue
                    if event.importance not in importance_levels:
                        continue
                    if countries and not self._country_allowed(event, countries):
                        continue
                    key = event.event_id or f"{event.time.isoformat()}|{event.event}|{event.country}"
                    merged[key] = event

        return list(merged.values())

    async def _fetch_forexfactory(
        self,
        from_date: str,
        to_date: str,
        importance_levels: List[str],
        countries: List[str],
    ) -> List[EconomicEvent]:
        impact_map = {
            "high": "high",
            "medium": "medium",
            "low": "low",
            "holiday": "low",
        }
        start = datetime.strptime(from_date, "%Y-%m-%d").date()
        end = datetime.strptime(to_date, "%Y-%m-%d").date()
        headers = {"User-Agent": "gold-trading-news-bot/1.1", "Accept": "application/json"}

        data = None
        last_err = None
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            for url in self.FF_WEEKLY_URLS:
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                    break
                except Exception as e:
                    last_err = e
                    logger.warning(f"Forex Factory fetch failed ({url}): {e}")
        if data is None:
            raise RuntimeError(f"Forex Factory weekly JSON unavailable: {last_err}")

        events: List[EconomicEvent] = []
        for item in data if isinstance(data, list) else []:
            impact = impact_map.get(str(item.get("impact", "")).lower(), "low")
            if impact not in importance_levels:
                continue
            ff_country = str(item.get("country", "")).upper()
            country = self.FF_CURRENCY_TO_COUNTRY.get(ff_country, ff_country)
            currency = ff_country if len(ff_country) == 3 else ""
            event = EconomicEvent(
                event=item.get("title") or "Unknown",
                time=datetime.now(self.tz),  # placeholder, set below
                timezone=self.settings.timezone,
                actual=self._safe_str(item.get("actual")),
                forecast=self._safe_str(item.get("forecast")),
                previous=self._safe_str(item.get("previous")),
                importance=impact,
                country=country,
                currency=currency,
                source="forexfactory",
            )
            date_str = item.get("date")
            if not date_str:
                continue
            try:
                dt = datetime.fromisoformat(str(date_str))
                if dt.tzinfo is None:
                    dt = pytz.timezone("America/New_York").localize(dt)
                dt = dt.astimezone(self.tz)
            except Exception:
                continue
            if not (start <= dt.date() <= end):
                continue
            if countries and not self._country_allowed(event, countries):
                continue
            event.time = dt
            event.event_id = f"ff:{dt.isoformat()}|{event.event}|{ff_country}"
            events.append(event)

        logger.info(f"Fetched {len(events)} economic events from Forex Factory")
        return events

    def _country_allowed(self, event: EconomicEvent, countries: List[str]) -> bool:
        if event.country in countries:
            return True
        if event.currency == "EUR" and "EU" in countries:
            return True
        if event.currency == "USD" and "US" in countries:
            return True
        return False

    def _parse_biquote_event(self, item: Dict) -> Optional[EconomicEvent]:
        try:
            time_str = item.get("time") or item.get("date") or item.get("datetime")
            if not time_str:
                return None
            if "T" in str(time_str):
                dt = datetime.fromisoformat(str(time_str).replace("Z", "+00:00"))
            else:
                dt = datetime.strptime(str(time_str)[:19], "%Y-%m-%d %H:%M:%S")
                dt = pytz.UTC.localize(dt) if dt.tzinfo is None else dt
            dt = dt.astimezone(self.tz)

            importance = str(item.get("importance", "medium")).lower()
            if importance in ("1", "low"):
                return None
            if importance in ("2",):
                importance = "medium"
            if importance in ("3",):
                importance = "high"
            if importance not in ("medium", "high"):
                return None

            return EconomicEvent(
                event=item.get("name") or item.get("event") or item.get("title") or "Unknown",
                time=dt,
                timezone=self.settings.timezone,
                actual=self._format_value(item.get("actual"), item.get("unit")),
                forecast=self._format_value(
                    item.get("forecast") or item.get("consensus"), item.get("unit")
                ),
                previous=self._format_value(
                    item.get("previous") or item.get("revisedPrevious"), item.get("unit")
                ),
                importance=importance,
                country=item.get("countryCode") or item.get("country") or "",
                currency=item.get("currency") or "",
                unit=item.get("unit") or "",
                source="biquote",
                event_id=str(item.get("id") or item.get("eventId") or ""),
            )
        except Exception as e:
            logger.debug(f"Parse event error: {e}")
            return None

    def _format_value(self, val, unit=None) -> Optional[str]:
        if val is None or val == "" or str(val).lower() in ("null", "none", "n/a"):
            return None
        text = str(val).strip()
        unit = (unit or "").lower()
        if unit in ("percent", "percentage", "%") and "%" not in text:
            return f"{text}%"
        return text

    def _safe_str(self, val) -> Optional[str]:
        if val is None or val == "" or str(val).lower() in ("null", "none", "n/a"):
            return None
        return str(val)

    def _assess_gold_impact(self, event: EconomicEvent) -> str:
        name = event.event.upper()
        delta = event.surprise_delta
        threshold = getattr(self.settings, "high_surprise_delta", 0.2)

        is_inflation = any(k in name for k in ["CPI", "PPI", "PCE", "INFLATION"])
        is_rate = any(k in name for k in ["RATE", "INTEREST", "FED", "FOMC", "SNB", "ECB", "BOJ"])
        is_jobs = any(
            k in name for k in ["NFP", "NON-FARM", "UNEMPLOYMENT", "PAYROLL", "JOBLESS", "CLAIMS"]
        )

        if delta is None:
            if event.importance == "high":
                return "รอประกาศจริง (High Impact)"
            return "รอประกาศจริง"

        if is_inflation or is_rate:
            if delta > threshold:
                return "🔴 มุมมองเชิงลบต่อทองคำ (Actual > Forecast → DXY แข็ง)"
            if delta < -threshold:
                return "🟢 มุมมองเชิงบวกต่อทองคำ (Actual < Forecast → DXY อ่อน)"
            return "🟡 ผลกระทบจำกัด (ใกล้เคียงคาดการณ์)"

        if is_jobs:
            if "UNEMPLOYMENT" in name:
                if delta > 0.1:
                    return "🟢 มุมมองเชิงบวกต่อทองคำ (ว่างงานสูงกว่าคาด)"
                if delta < -0.1:
                    return "🔴 มุมมองเชิงลบต่อทองคำ (ว่างงานต่ำกว่าคาด)"
            elif "CLAIMS" in name or "JOBLESS" in name:
                if delta > 0:
                    return "🟢 มุมมองเชิงบวกต่อทองคำ (Claims สูงกว่าคาด)"
                if delta < 0:
                    return "🔴 มุมมองเชิงลบต่อทองคำ (Claims ต่ำกว่าคาด)"
            else:
                if delta > 0:
                    return "🔴 มุมมองเชิงลบต่อทองคำ (Jobs แข็งแกร่ง)"
                if delta < 0:
                    return "🟢 มุมมองเชิงบวกต่อทองคำ (Jobs อ่อนแอ)"

        if abs(delta) > threshold:
            return "⚠️ Surprise สูง – ติดตามความผันผวน"
        return "ผลกระทบปานกลาง"

    def filter_high_impact(self, events: List[EconomicEvent]) -> List[EconomicEvent]:
        return [e for e in events if e.importance == "high"]

    def filter_medium_high(self, events: List[EconomicEvent]) -> List[EconomicEvent]:
        return [e for e in events if e.importance in ("medium", "high")]
