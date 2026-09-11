"""
ขั้นตอนที่ 1: Economic Calendar Scan
ดึงข้อมูลปฏิทินเศรษฐกิจ Medium (2 ดาว) และ High (3 ดาว)
"""
from __future__ import annotations

import httpx
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
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
    impact_on_gold: str = ""  # positive / negative / neutral / high_negative etc.

    def calculate_surprise(self) -> Optional[float]:
        """Surprise Delta = Actual - Forecast"""
        if self.actual is None or self.forecast is None:
            return None
        try:
            # Clean percentage and number strings
            def clean(val: str) -> float:
                v = str(val).replace("%", "").replace(",", "").strip()
                if v in ("", "-", "—", "N/A"):
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
        }


class CalendarScanner:
    """
    Scanner สำหรับ Economic Calendar
    ใช้แหล่งฟรี: biquote.io (primary) + fallback
    """

    def __init__(self):
        self.settings = get_settings()
        self.tz = pytz.timezone(self.settings.timezone)
        self.base_url = "https://biquote.io/api/calendar"

    async def fetch_events(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        importance: List[str] = None,
        countries: List[str] = None,
    ) -> List[EconomicEvent]:
        """
        ดึงข้อมูลปฏิทินเศรษฐกิจ
        importance: ["medium", "high"] ตามสเปค
        """
        if importance is None:
            importance = ["medium", "high"]
        if countries is None:
            countries = self.settings.focus_countries

        if from_date is None:
            from_date = datetime.now(self.tz).strftime("%Y-%m-%d")
        if to_date is None:
            to_date = (datetime.now(self.tz) + timedelta(days=1)).strftime("%Y-%m-%d")

        params = {
            "from": from_date,
            "to": to_date,
            "importance": ",".join(importance),
            "countries": ",".join(countries),
        }

        events: List[EconomicEvent] = []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(self.base_url, params=params)
                resp.raise_for_status()
                data = resp.json()

                if isinstance(data, list):
                    for item in data:
                        event = self._parse_event(item)
                        if event:
                            events.append(event)
                elif isinstance(data, dict) and "data" in data:
                    for item in data["data"]:
                        event = self._parse_event(item)
                        if event:
                            events.append(event)

            logger.info(f"Fetched {len(events)} economic events from biquote")
        except Exception as e:
            logger.warning(f"biquote API failed: {e}. Using fallback sample data.")
            events = self._get_fallback_events()

        # Calculate surprise & impact
        for ev in events:
            ev.calculate_surprise()
            ev.impact_on_gold = self._assess_gold_impact(ev)

        return sorted(events, key=lambda x: x.time or datetime.min)

    def _parse_event(self, item: Dict) -> Optional[EconomicEvent]:
        try:
            time_str = item.get("time") or item.get("date") or item.get("datetime")
            if time_str:
                if "T" in str(time_str):
                    dt = datetime.fromisoformat(str(time_str).replace("Z", "+00:00"))
                else:
                    dt = datetime.strptime(str(time_str)[:19], "%Y-%m-%d %H:%M:%S")
                dt = dt.astimezone(self.tz)
            else:
                dt = datetime.now(self.tz)

            importance = str(item.get("importance", "medium")).lower()
            if importance not in ("medium", "high"):
                # filter only medium/high
                if importance in ("1", "low"):
                    return None
                if importance in ("2",):
                    importance = "medium"
                if importance in ("3",):
                    importance = "high"

            return EconomicEvent(
                event=item.get("name") or item.get("event") or item.get("title") or "Unknown",
                time=dt,
                timezone=self.settings.timezone,
                actual=self._safe_str(item.get("actual")),
                forecast=self._safe_str(item.get("forecast") or item.get("consensus")),
                previous=self._safe_str(item.get("previous")),
                importance=importance,
                country=item.get("countryCode") or item.get("country") or "",
                currency=item.get("currency") or "",
                unit=item.get("unit") or "",
            )
        except Exception as e:
            logger.debug(f"Parse event error: {e}")
            return None

    def _safe_str(self, val) -> Optional[str]:
        if val is None or val == "" or str(val).lower() in ("null", "none", "n/a"):
            return None
        return str(val)

    def _assess_gold_impact(self, event: EconomicEvent) -> str:
        """
        ตามกฎในสเปค:
        Actual > Forecast ในกลุ่ม CPI / Interest Rate = ส่งผลบวกต่อ DXY / ส่งผลลบต่อ ทองคำ
        """
        name = event.event.upper()
        delta = event.surprise_delta

        is_inflation = any(k in name for k in ["CPI", "PPI", "PCE", "INFLATION"])
        is_rate = any(k in name for k in ["RATE", "INTEREST", "FED", "FOMC"])
        is_jobs = any(k in name for k in ["NFP", "NON-FARM", "UNEMPLOYMENT", "PAYROLL"])

        if delta is None:
            if event.importance == "high":
                return "รอประกาศจริง (High Impact)"
            return "รอประกาศจริง"

        if is_inflation or is_rate:
            if delta > self.settings.high_surprise_delta:
                return "🔴 มุมมองเชิงลบต่อทองคำ (Actual > Forecast → DXY แข็ง)"
            elif delta < -self.settings.high_surprise_delta:
                return "🟢 มุมมองเชิงบวกต่อทองคำ (Actual < Forecast → DXY อ่อน)"
            else:
                return "🟡 ผลกระทบจำกัด (ใกล้เคียงคาดการณ์)"

        if is_jobs:
            # Strong jobs = hawkish = negative for gold
            if "UNEMPLOYMENT" in name:
                # Higher unemployment = dovish = positive for gold
                if delta > 0.1:
                    return "🟢 มุมมองเชิงบวกต่อทองคำ (ว่างงานสูงกว่าคาด)"
                elif delta < -0.1:
                    return "🔴 มุมมองเชิงลบต่อทองคำ (ว่างงานต่ำกว่าคาด)"
            else:
                if delta > 0:
                    return "🔴 มุมมองเชิงลบต่อทองคำ (Jobs แข็งแกร่ง)"
                elif delta < 0:
                    return "🟢 มุมมองเชิงบวกต่อทองคำ (Jobs อ่อนแอ)"

        if abs(delta) > self.settings.high_surprise_delta:
            return "⚠️ Surprise สูง – ติดตามความผันผวน"
        return "ผลกระทบปานกลาง"

    def _get_fallback_events(self) -> List[EconomicEvent]:
        """Fallback เมื่อ API ล้มเหลว – ใช้ข้อมูลตัวอย่างเพื่อให้ระบบทำงานต่อได้"""
        now = datetime.now(self.tz)
        return [
            EconomicEvent(
                event="US Core CPI (MoM)",
                time=now.replace(hour=19, minute=30, second=0, microsecond=0),
                timezone=self.settings.timezone,
                actual=None,
                forecast="0.3%",
                previous="0.2%",
                importance="high",
                country="US",
                currency="USD",
            ),
            EconomicEvent(
                event="US Initial Jobless Claims",
                time=now.replace(hour=19, minute=30, second=0, microsecond=0),
                timezone=self.settings.timezone,
                actual=None,
                forecast="230K",
                previous="231K",
                importance="medium",
                country="US",
                currency="USD",
            ),
        ]

    def filter_high_impact(self, events: List[EconomicEvent]) -> List[EconomicEvent]:
        return [e for e in events if e.importance == "high"]

    def filter_medium_high(self, events: List[EconomicEvent]) -> List[EconomicEvent]:
        return [e for e in events if e.importance in ("medium", "high")]
