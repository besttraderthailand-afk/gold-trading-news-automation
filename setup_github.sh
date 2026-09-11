#!/bin/bash
# ============================================
# วิธีสร้าง Repo บน GitHub และ Push โค้ดนี้ขึ้นไป
# ============================================

set -e

echo "🥇 Gold Trading News Automation - GitHub Setup"
echo "=============================================="

# 1. ตรวจสอบว่ามี git หรือยัง
if ! command -v git &> /dev/null; then
    echo "❌ กรุณาติดตั้ง git ก่อน"
    exit 1
fi

# 2. Init git (ถ้ายังไม่มี)
if [ ! -d .git ]; then
    git init
    echo "✅ git init เรียบร้อย"
fi

# 3. Add files
git add .
git commit -m "Initial commit: Gold Trading News Automation System

- Economic Calendar Scanner (Medium + High Impact)
- Real-time Flash News Scanner
- Multi-Asset Impact Matrix for XAUUSD
- Telegram Daily Report @ 07:00 ICT
- Telegram Flash News Alerts
- Full report template
- Docker support
- Safety rules & Not Financial Advice disclaimer
" || echo "Already committed or nothing to commit"

echo ""
echo "=============================================="
echo "📌 ขั้นตอนถัดไป (ทำบนเครื่องคุณ):"
echo ""
echo "1. ไปที่ https://github.com/new"
echo "   สร้าง repo ชื่อ: gold-trading-news-automation"
echo "   (Public หรือ Private ตามต้องการ)"
echo ""
echo "2. รันคำสั่งเหล่านี้:"
echo ""
echo "   git remote add origin https://github.com/YOUR_USERNAME/gold-trading-news-automation.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "3. อย่าลืมสร้างไฟล์ config/.env จาก .env.example"
echo "   แล้วใส่ TELEGRAM_BOT_TOKEN และ TELEGRAM_CHAT_ID"
echo ""
echo "4. รันด้วย Docker:"
echo "   docker-compose up -d"
echo ""
echo "หรือรันตรงๆ:"
echo "   python -m src.main --mode scheduler"
echo "=============================================="
