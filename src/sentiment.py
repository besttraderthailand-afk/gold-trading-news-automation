"""
Financial Sentiment Analysis for Gold Trading News
Rule-based + Lexicon approach (no heavy ML dependency)
Optimized for monetary policy, inflation, geopolitics & gold impact
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple, Optional
from enum import Enum


class SentimentLabel(str, Enum):
    VERY_BULLISH = "very_bullish"   # แข็งแกร่งมากสำหรับทอง
    BULLISH = "bullish"             # บวกต่อทอง
    NEUTRAL = "neutral"
    BEARISH = "bearish"             # ลบต่อทอง
    VERY_BEARISH = "very_bearish"   # ลบมากต่อทอง


@dataclass
class SentimentResult:
    label: SentimentLabel
    score: float          # -1.0 (very bearish) → +1.0 (very bullish) สำหรับทอง
    confidence: float     # 0.0 – 1.0
    matched_phrases: List[str]
    gold_bias: str        # "positive" | "negative" | "neutral"
    summary_th: str
    summary_en: str

    @property
    def emoji(self) -> str:
        mapping = {
            SentimentLabel.VERY_BULLISH: "🟢🟢",
            SentimentLabel.BULLISH: "🟢",
            SentimentLabel.NEUTRAL: "⚪",
            SentimentLabel.BEARISH: "🔴",
            SentimentLabel.VERY_BEARISH: "🔴🔴",
        }
        return mapping.get(self.label, "⚪")

    @property
    def label_th(self) -> str:
        mapping = {
            SentimentLabel.VERY_BULLISH: "บวกแรงมากต่อทองคำ",
            SentimentLabel.BULLISH: "บวกต่อทองคำ",
            SentimentLabel.NEUTRAL: "เป็นกลาง",
            SentimentLabel.BEARISH: "ลบต่อทองคำ",
            SentimentLabel.VERY_BEARISH: "ลบแรงมากต่อทองคำ",
        }
        return mapping.get(self.label, "เป็นกลาง")


class GoldSentimentAnalyzer:
    """
    Sentiment Analyzer ที่โฟกัสผลกระทบต่อทองคำ (XAUUSD)
    
    Logic หลัก:
    - Dovish Fed / Rate Cut / Weak Jobs / Low Inflation  → Bullish Gold
    - Hawkish Fed / Rate Hike / Strong Jobs / Hot CPI   → Bearish Gold
    - Geopolitical risk / War / Sanctions               → Bullish Gold (safe-haven)
    - Strong USD / Risk-on                              → Bearish Gold
    """

    def __init__(self):
        # === Phrases ที่เป็นบวกต่อทองคำ (score +) ===
        self.bullish_phrases = {
            # Monetary Policy - Dovish
            r"\brate cut\b": 0.85,
            r"\bcuts rates?\b": 0.85,
            r"\blower rates?\b": 0.70,
            r"\bdovish\b": 0.80,
            r"\bpivot\b": 0.65,
            r"\beasing\b": 0.70,
            r"\bqe\b|\bquantitative easing\b": 0.75,
            r"\bholds rates?\b": 0.15,          # neutral-slightly positive vs hike
            r"\bno hike\b": 0.40,
            r"\bskip(s|ping)? (a |the )?hike\b": 0.50,

            # Inflation cooling
            r"\binflation cools?\b": 0.70,
            r"\bcooling inflation\b": 0.70,
            r"\binflation slows?\b": 0.65,
            r"\binflation falls?\b": 0.70,
            r"\binflation eases?\b": 0.65,
            r"\bsoft(er)? (cpi|pce|inflation)\b": 0.60,
            r"\bbelow (expectations?|forecasts?|estimates?)\b": 0.45,

            # Weak labor / recession fears
            r"\bweak(er)? jobs?\b": 0.55,
            r"\bjobs? miss\b": 0.60,
            r"\bunemployment rises?\b": 0.55,
            r"\bhigher unemployment\b": 0.55,
            r"\brecession\b": 0.50,
            r"\bsoft landing\b": 0.30,

            # Geopolitics / Safe-haven
            r"\bwar\b|\bconflict\b|\binvasion\b": 0.70,
            r"\bsanctions?\b": 0.45,
            r"\bmiddle east\b|\bisrael\b|\biran\b|\bgaza\b": 0.55,
            r"\btension(s)?\b": 0.40,
            r"\bgeopolitical\b": 0.50,
            r"\bsafe[- ]?haven\b": 0.80,
            r"\brisk[- ]?off\b": 0.55,
            r"\bflight to safety\b": 0.70,

            # USD weakness
            r"\bdollar falls?\b|\bdollar drops?\b|\bdollar weak(ens|ness)?\b": 0.65,
            r"\bdxy falls?\b|\bdxy drops?\b": 0.65,
            r"\busd weak\b": 0.60,

            # Direct gold positive
            r"\bgold rises?\b|\bgold surges?\b|\bgold rall(y|ies)\b": 0.90,
            r"\bgold hits?\b.*high": 0.85,
            r"\bbullion\b": 0.30,
        }

        # === Phrases ที่เป็นลบต่อทองคำ (score -) ===
        self.bearish_phrases = {
            # Monetary Policy - Hawkish
            r"\brate hike\b": -0.85,
            r"\bhikes rates?\b": -0.85,
            r"\braises rates?\b": -0.85,
            r"\bhigher rates?\b": -0.70,
            r"\bhawkish\b": -0.80,
            r"\btightening\b": -0.70,
            r"\bqt\b|\bquantitative tightening\b": -0.65,
            r"\bhigher for longer\b": -0.75,
            r"\bno cut\b|\bskip(s|ping)? (a |the )?cut\b": -0.40,

            # Hot inflation
            r"\bhot (cpi|pce|inflation)\b": -0.75,
            r"\binflation surges?\b|\binflation jumps?\b": -0.80,
            r"\binflation rises?\b|\binflation accelerates?\b": -0.70,
            r"\bsticky inflation\b": -0.60,
            r"\babove (expectations?|forecasts?|estimates?)\b": -0.50,
            r"\bcpi beats?\b|\bpce beats?\b": -0.55,

            # Strong labor
            r"\bstrong(er)? jobs?\b": -0.55,
            r"\bjobs? beat\b|\bnfp beats?\b": -0.60,
            r"\bunemployment falls?\b|\blower unemployment\b": -0.50,
            r"\btight labor\b": -0.45,

            # USD strength / Risk-on
            r"\bdollar rises?\b|\bdollar surges?\b|\bdollar strength\b": -0.65,
            r"\bdxy rises?\b|\bdxy surges?\b": -0.65,
            r"\busd strong\b": -0.60,
            r"\brisk[- ]?on\b": -0.45,
            r"\brisk appetite\b": -0.40,

            # Direct gold negative
            r"\bgold falls?\b|\bgold drops?\b|\bgold slides?\b": -0.90,
            r"\bgold plunges?\b|\bgold tumbles?\b": -0.95,
            r"\bgold hits?\b.*low": -0.85,
        }

        # Intensifiers
        self.intensifiers = {
            r"\bsharply\b|\bsteeply\b|\bdramatically\b": 1.3,
            r"\bsurprise(s|d)?\b|\bunexpected(ly)?\b": 1.25,
            r"\brecord\b|\bhistoric(al)?\b": 1.2,
            r"\bslight(ly)?\b|\bmild(ly)?\b": 0.7,
            r"\bmodest(ly)?\b": 0.75,
        }

        # Negation
        self.negations = [
            r"\bnot\b", r"\bno\b", r"\bnever\b", r"\bwithout\b",
            r"\bfail(s|ed|ing)? to\b", r"\bunlikely\b", r"\bdoubt\b",
        ]

    def analyze(self, text: str, category: str = "") -> SentimentResult:
        if not text or not text.strip():
            return self._neutral_result()

        text_lower = text.lower()
        score = 0.0
        matched: List[str] = []
        weight_sum = 0.0

        # Score bullish phrases
        for pattern, base_score in self.bullish_phrases.items():
            matches = list(re.finditer(pattern, text_lower, re.IGNORECASE))
            for m in matches:
                adj_score = self._adjust_score(base_score, text_lower, m.start())
                score += adj_score
                weight_sum += abs(adj_score)
                matched.append(m.group())

        # Score bearish phrases
        for pattern, base_score in self.bearish_phrases.items():
            matches = list(re.finditer(pattern, text_lower, re.IGNORECASE))
            for m in matches:
                adj_score = self._adjust_score(base_score, text_lower, m.start())
                score += adj_score
                weight_sum += abs(adj_score)
                matched.append(m.group())

        # Category bias boost
        score = self._apply_category_bias(score, category, text_lower)

        # Normalize
        if weight_sum > 0:
            # Soft normalize to keep in [-1, 1]
            norm_score = max(-1.0, min(1.0, score / max(weight_sum * 0.6, 1.0)))
        else:
            norm_score = 0.0

        # Confidence based on number of matches + strength
        confidence = min(1.0, 0.35 + (len(matched) * 0.15) + (abs(norm_score) * 0.4))

        label = self._score_to_label(norm_score)
        gold_bias = "positive" if norm_score > 0.15 else "negative" if norm_score < -0.15 else "neutral"

        summary_th, summary_en = self._build_summaries(label, matched, category)

        return SentimentResult(
            label=label,
            score=round(norm_score, 3),
            confidence=round(confidence, 3),
            matched_phrases=list(dict.fromkeys(matched))[:8],  # unique, max 8
            gold_bias=gold_bias,
            summary_th=summary_th,
            summary_en=summary_en,
        )

    def _adjust_score(self, base: float, text: str, pos: int) -> float:
        """Apply intensifiers and negations around the match"""
        window_start = max(0, pos - 40)
        window = text[window_start:pos + 40]

        # Intensifier
        multiplier = 1.0
        for pat, mult in self.intensifiers.items():
            if re.search(pat, window, re.IGNORECASE):
                multiplier = mult
                break

        # Negation → flip sign
        for neg in self.negations:
            if re.search(neg, window, re.IGNORECASE):
                return -base * multiplier * 0.85

        return base * multiplier

    def _apply_category_bias(self, score: float, category: str, text: str) -> float:
        """Light category prior"""
        if category == "geopolitics":
            # Geopolitical risk generally supports gold
            if score >= 0:
                score += 0.15
            else:
                score *= 0.7  # reduce bearish weight in geo context
        elif category == "monetary":
            # Already heavily covered by phrases
            pass
        elif category == "inflation":
            pass
        return score

    def _score_to_label(self, score: float) -> SentimentLabel:
        if score >= 0.55:
            return SentimentLabel.VERY_BULLISH
        if score >= 0.18:
            return SentimentLabel.BULLISH
        if score <= -0.55:
            return SentimentLabel.VERY_BEARISH
        if score <= -0.18:
            return SentimentLabel.BEARISH
        return SentimentLabel.NEUTRAL

    def _build_summaries(
        self, label: SentimentLabel, matched: List[str], category: str
    ) -> Tuple[str, str]:
        th_map = {
            SentimentLabel.VERY_BULLISH: "ข่าวนี้ส่งสัญญาณบวกแรงต่อทองคำ",
            SentimentLabel.BULLISH: "ข่าวนี้มีแนวโน้มบวกต่อทองคำ",
            SentimentLabel.NEUTRAL: "ข่าวนี้มีผลกระทบจำกัดต่อทองคำ",
            SentimentLabel.BEARISH: "ข่าวนี้มีแนวโน้มกดดันราคาทองคำ",
            SentimentLabel.VERY_BEARISH: "ข่าวนี้ส่งสัญญาณลบแรงต่อทองคำ",
        }
        en_map = {
            SentimentLabel.VERY_BULLISH: "Strongly bullish signal for gold",
            SentimentLabel.BULLISH: "Moderately bullish for gold",
            SentimentLabel.NEUTRAL: "Limited impact on gold",
            SentimentLabel.BEARISH: "Moderately bearish pressure on gold",
            SentimentLabel.VERY_BEARISH: "Strongly bearish signal for gold",
        }

        th = th_map[label]
        en = en_map[label]

        if matched:
            key_phrases = ", ".join(matched[:3])
            th += f" (คำสำคัญ: {key_phrases})"
            en += f" (key: {key_phrases})"

        return th, en

    def _neutral_result(self) -> SentimentResult:
        return SentimentResult(
            label=SentimentLabel.NEUTRAL,
            score=0.0,
            confidence=0.0,
            matched_phrases=[],
            gold_bias="neutral",
            summary_th="ไม่มีข้อมูลเพียงพอในการวิเคราะห์ sentiment",
            summary_en="Insufficient data for sentiment analysis",
        )


# Singleton for convenience
_analyzer: Optional[GoldSentimentAnalyzer] = None


def get_sentiment_analyzer() -> GoldSentimentAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = GoldSentimentAnalyzer()
    return _analyzer


def analyze_sentiment(text: str, category: str = "") -> SentimentResult:
    return get_sentiment_analyzer().analyze(text, category)
