"""
Configuration settings for Gold Trading News Automation
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Telegram
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(..., env="TELEGRAM_CHAT_ID")

    # Optional API Keys
    news_api_key: str = Field(default="", env="NEWS_API_KEY")
    finnhub_api_key: str = Field(default="", env="FINNHUB_API_KEY")
    alpha_vantage_key: str = Field(default="", env="ALPHA_VANTAGE_KEY")

    # Timezone
    timezone: str = Field(default="Asia/Bangkok", env="TIMEZONE")

    # Scheduler
    daily_report_hour: int = Field(default=7, env="DAILY_REPORT_HOUR")
    daily_report_minute: int = Field(default=0, env="DAILY_REPORT_MINUTE")
    flash_check_interval_minutes: int = Field(default=5, env="FLASH_CHECK_INTERVAL_MINUTES")

    # Thresholds
    high_surprise_delta: float = Field(default=0.2, env="HIGH_SURPRISE_DELTA")
    gold_volatility_threshold: float = Field(default=20.0, env="GOLD_VOLATILITY_THRESHOLD")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # Keywords for Flash News (from the original spec)
    monetary_policy_keywords: List[str] = [
        "Interest Rate", "Rate Cut", "Rate Hike", "FOMC", "Dot Plot",
        "Balance Sheet", "Fed", "Powell", "BOJ", "ECB", "PBOC"
    ]
    inflation_jobs_keywords: List[str] = [
        "CPI", "PPI", "PCE", "Non-Farm Payrolls", "NFP", "Unemployment Rate",
        "Inflation", "Jobs Report"
    ]
    geopolitics_keywords: List[str] = [
        "War", "Sanctions", "Tariff", "Conflict", "Middle East", "Military",
        "Geopolitical", "Attack", "Invasion"
    ]
    energy_keywords: List[str] = [
        "OPEC", "Crude Inventory", "Supply Disruption", "Production Cut",
        "Oil", "Brent", "WTI"
    ]
    crypto_tech_keywords: List[str] = [
        "Bitcoin ETF", "Crypto Regulation", "Halving", "Tech Earnings",
        "Bitcoin", "Ethereum"
    ]

    # High impact countries / currencies focus
    focus_countries: List[str] = ["US", "EU", "GB", "JP", "CN", "AU", "CA"]

    class Config:
        env_file = str(BASE_DIR / "config" / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


def get_settings() -> Settings:
    return Settings()
