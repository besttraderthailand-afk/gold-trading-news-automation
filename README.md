# 🥇 Gold Trading News Automation System

**ระบบ Automation สแกนปฏิทินเศรษฐกิจ + ข่าวด่วน + วิเคราะห์ผลกระทบ Multi-Asset สำหรับทองคำ (XAUUSD)**

ระบบนี้ทำตามสเปคที่กำหนดไว้ครบถ้วน:
- **ขั้นตอนที่ 1**: Economic Calendar Scan (Medium + High Impact)
- **ขั้นตอนที่ 2**: Real-time Flash News Scan
- **ขั้นตอนที่ 3**: Multi-Asset Impact Matrix
- **Telegram Automation**: Daily Report 07:00 น. (ICT) + Flash News Alert

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📅 Economic Calendar | ดึงข้อมูล Medium/High Impact จากแหล่งฟรี (biquote + fallback) |
| 📊 Surprise Delta | คำนวณ `Actual - Forecast` และประเมินผลกระทบต่อทองคำ |
| 🚨 Flash News | สแกนข่าวด่วนจาก Bloomberg / Reuters / Fed / BOJ / ECB keywords |
| 🧠 Sentiment Analysis | วิเคราะห์ sentiment ต่อทองคำ (Bullish/Bearish) แบบ Financial-aware |
| 🎯 Impact Matrix | High / Medium / Low impact classification สำหรับ XAUUSD |
| 📱 Telegram Bot | Daily Report + Real-time Alert พร้อม Markdown + Sentiment |
| ⏰ Scheduler | รัน Daily Report ทุกวัน 07:00 น. เวลาประเทศไทย (UTC+7) |
| 🛡️ Safety Rules | Fact-based, Deduplication, Not Financial Advice disclaimer |

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/gold-trading-news-automation.git
cd gold-trading-news-automation
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configuration

คัดลอกไฟล์ config:

```bash
cp config/.env.example config/.env
```

แก้ไข `config/.env`:

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Optional: News API keys (ถ้ามี)
NEWS_API_KEY=
FINNHUB_API_KEY=

# Timezone
TIMEZONE=Asia/Bangkok
```

### 3. วิธีสร้าง Telegram Bot

1. เปิด Telegram คุยกับ [@BotFather](https://t.me/BotFather)
2. พิมพ์ `/newbot` → ตั้งชื่อบอท
3. คัดลอก **Token** มาใส่ใน `.env`
4. หา Chat ID:
   - ส่งข้อความหาบอท
   - เปิด `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - หา `"chat":{"id": xxxxx}`

### 4. รันระบบ

**รัน Daily Report ครั้งเดียว (ทดสอบ):**
```bash
python -m src.main --mode daily
```

**รัน Flash News Monitor:**
```bash
python -m src.main --mode flash
```

**รัน Full Scheduler (แนะนำ production):**
```bash
python -m src.main --mode scheduler
```

**Docker (แนะนำ):**
```bash
docker-compose up -d
```

---

## 📁 โครงสร้างโปรเจกต์

```
gold-trading-news-automation/
├── config/
│   ├── .env.example
│   └── settings.py
├── src/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── calendar_scanner.py     # ขั้นตอนที่ 1
│   ├── news_scanner.py         # ขั้นตอนที่ 2
│   ├── sentiment.py            # 🧠 Financial Sentiment Analysis
│   ├── impact_analyzer.py      # ขั้นตอนที่ 3
│   ├── telegram_bot.py         # Telegram sender
│   ├── scheduler.py            # Daily + Flash scheduler
│   └── utils.py
├── tests/
├── docs/
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## 📊 ตัวอย่าง Daily Report (Telegram)

```
📊 *สรุปภาวะตลาดและข่าวสารการลงทุนประจำวัน*
📅 ประจำวันที่: 11/09/2026 | ⏰ 07:00 น.
🎯 *สินทรัพย์หลัก:* ทองคำ (XAUUSD)
📉 *ดัชนีดอลลาร์ (DXY):* ทรงตัว (101.25)

---
🔴 *ข่าวผลกระทบสูง (High Impact):*
• US CPI เกินคาด +0.3% → กดดันทองคำระยะสั้น

🗓️ *ปฏิทินเศรษฐกิจน่าจับตาวันนี้:*
• 19:30 US Core CPI (MoM) | คาดการณ์: 0.3% (ผลกระทบ: High)

💡 *กลยุทธ์ประจำวัน:* ระวังความผันผวนช่วงข่าว CPI, ลด size หรือรอ confirmation
```

---

## 🚨 ตัวอย่าง Flash News Alert (พร้อม Sentiment)

```
🚨 *[FLASH NEWS] แจ้งเตือนข่าวด่วนส่งผลกระทบสูง*

📌 *ข่าว:* Fed ลดดอกเบี้ย 25 bps (Fed cuts rates by 25bps)
🏛️ *แหล่งข่าว:* Reuters | ⏰ 02:00
📊 *ตัวเลขจริง vs คาดการณ์:* Actual: 5.25% | Forecast: 5.50%
📈 *Sentiment:* 🟢🟢 บวกแรงมากต่อทองคำ (score +0.82 | conf 92%)
🔑 *Keywords:* rate cut, dovish

💡 *บทวิเคราะห์ต่อ [ทองคำ]:*
🟢🟢 ข่าวนี้ส่งสัญญาณบวกแรงต่อทองคำ (คำสำคัญ: rate cut, dovish)

⚠️ *โปรดเพิ่มความระมัดระวังและบริหารความเสี่ยงในพอร์ตการลงทุน*
```

---

## 🧠 Sentiment Analysis

ระบบใช้ **Financial-aware Rule-based Sentiment** ที่ออกแบบมาเฉพาะสำหรับทองคำ:

| สัญญาณ | ผลต่อทองคำ | ตัวอย่าง |
|--------|-------------|---------|
| Rate Cut / Dovish Fed | 🟢 Bullish | "Fed cuts rates", "dovish pivot" |
| Rate Hike / Hawkish | 🔴 Bearish | "Fed hikes", "higher for longer" |
| Hot CPI / Strong Jobs | 🔴 Bearish | "CPI surges", "NFP beats" |
| Cooling Inflation / Weak Jobs | 🟢 Bullish | "inflation cools", "jobs miss" |
| Geopolitical Risk | 🟢 Bullish (Safe-haven) | "war", "sanctions", "Middle East" |
| Strong USD | 🔴 Bearish | "dollar surges", "DXY rises" |

Score อยู่ระหว่าง **-1.0 (ลบสุด)** ถึง **+1.0 (บวกสุด)** ต่อทองคำ

---

## ⚙️ Configuration เพิ่มเติม

ใน `config/settings.py` สามารถปรับ:
- ระดับ Importance ที่ต้องการสแกน
- Keywords สำหรับ Flash News
- Threshold สำหรับ Surprise Delta
- ช่วงเวลาตรวจสอบ Flash News (default ทุก 5 นาที)

---

## 🛡️ Disclaimer

การวิเคราะห์ทุกครั้งจัดทำขึ้นเพื่อการให้ข้อมูลเท่านั้น  
**ไม่ถือเป็นคำแนะนำทางการเงินหรือคำชวนลงทุน (Not Financial Advice)**

---

## 📜 License

MIT License – ใช้งานได้อย่างอิสระ

---

สร้างโดยระบบตามสเปคที่คุณกำหนดไว้ 100%  
พร้อมใช้งานบน GitHub + Telegram Automation

## 🧪 Economic Calendar E2E Test

GitHub Actions workflow:

`.github/workflows/economic_calendar_e2e.yml`

Pipeline:

`Economic Calendar → Date Validation → Medium/High Filter → Thai Formatter → Telegram`

Run manually from **GitHub → Actions → Economic Calendar E2E Test → Run workflow**.

The workflow also runs at **07:00 Asia/Bangkok, Monday-Friday** (00:00 UTC) as a smoke test. It refuses to send a calendar message when no verified events are returned, preventing fallback/sample data from being presented as real calendar data.
