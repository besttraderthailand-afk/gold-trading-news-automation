# Nexttrade Combined Architecture

เอกสารนี้ชุดเดียวกันในทุก repo — อธิบายระบบเมื่อประกอบกัน ไม่ใช่สเปกของ repo เดียว

อัปเดต: 2026-10-01

## 1. หลักการ

Server แจกสิทธิ์และแพ็กเกจ Client  
Client วิเคราะห์ / คำนวณ / ยิงออเดอร์บนเครื่องลูกค้า  
Dashboard เป็นชั้นควบคุมและแสดงผล **ไม่ใช่สมองเทรด**  
EA เป็นผู้ execute จริง Python ไม่ยิงออเดอร์เอง  
คีย์ LLM อยู่ที่เครื่องลูกค้า ไม่เก็บฝั่งผู้พัฒนา

โหมดปลอดภัยเริ่มต้น: `advise` / `analyze_only=true` / `auto_trade=false`

## 2. แผนที่ repo

| ชั้น | Repo | Visibility | บทบาทเมื่อรวมระบบ |
|---|---|---|---|
| Presentation | `Web-AI-Dashboard-Nexttrade` | public | หน้าลูกค้า, ชั้นควบคุม SNAP, license/signal UI |
| Control plane | `nexttrade-backend` | private | สแกนตลาด, ปฏิทินข่าว, กฎกลาง, แจ้งเตือน, MCP |
| License / multi-EA | `NexxTrade-EA-Admin-Private` | private | registry EA, license header, telemetry, admin API |
| Client runtime | `Nexttrade-AI-Agent` | private | สะพาน Python `:8787` + EA ที่แจกลูกค้า |
| Client runtime (graph) | `Nexttrade-AI-Agent-langgraph` | private | สายถัดไป: LangGraph trade + review + COT |
| Server multi-agent | `nexttrade-agent-system` | private | วางแผน / รีวิวข้ามโมเดล / risk gate (TS) |
| Support | `NEXTTRADE_LINE_AI` | private | LINE OA ซัพพอร์ตลูกค้า |
| Research | `nexttrade-mc-wfo` | private | Monte Carlo + walk-forward จากล็อกเทรด |
| Research | `gold-trading-news-automation` | public | สแกนข่าวทอง / ปฏิทิน |

ชุดแจกลูกค้า `Nexttrade-AI-Agent-Client-Setup.zip` = Release ของ `Nexttrade-AI-Agent` ไม่ใช่ repo แยก

## 3. ภาพรวมเมื่อรวมกัน

```text
                    ┌─────────────────────────────────────────┐
                    │  SERVER (คุณถือ)                         │
                    │                                         │
  ลูกค้าเปิดเว็บ ──►│  Web-AI-Dashboard-Nexttrade             │
  แอดมินเปิดคอนโซล  │   index / control / console / ai-chart  │
                    │   signal-api (license + subscription)   │
                    │                 │                       │
                    │                 ▼                       │
                    │  nexttrade-backend :8000                │
                    │   /scan /news /rules /audit /notify     │
                    │   MCP tools                             │
                    │                 │                       │
                    │  NexxTrade-EA-Admin-Private             │
                    │   license issue/revoke + EA registry    │
                    │                                         │
                    │  nexttrade-agent-system (optional)      │
                    │   planner → creator/reviewer → risk     │
                    └─────────────────┬───────────────────────┘
                                      │ แจก ZIP + license key
                                      ▼
                    ┌─────────────────────────────────────────┐
                    │  CLIENT PC (ลูกค้าถือ)                   │
                    │                                         │
                    │  python -m agent.server  → :8787        │
                    │    regime / news / guardrails           │
                    │    orchestrator หรือ LangGraph          │
                    │    providers: OpenAI/Anthropic/Gemini/xAI│
                    │    หรือ local rules                     │
                    │                 ▲                       │
                    │                 │ WebRequest localhost   │
                    │  MT5 EA  NexttradeAIAgent.mq5           │
                    │    วาดการ์ด / คุม Engine START-STOP     │
                    │    เป็นคนส่งออเดอร์ (advise/semi/auto)  │
                    └─────────────────────────────────────────┘
```

## 4. กระแสข้อมูลหลัก

### 4.1 วิเคราะห์และคำนวณออเดอร์ (เส้นเทรด)

1. EA เก็บ snapshot: ราคา, สเปรด, equity, heat, แท่ง H1
2. `POST http://127.0.0.1:8787/propose`
3. Client agent
   - คำนวณ regime / ข่าว / session
   - เรียก LLM หรือกฎ local
   - ตัดด้วย guardrails (risk %, heat, DD, news HOLD)
   - คืนการ์ด BIAS / RISK / SESSION / PLAN + JSON ข้อเสนอ
4. EA
   - `advise` = แสดงการ์ดอย่างเดียว
   - `semi_auto` = รอคนกด CONFIRM
   - `auto` = ยิงออเดอร์ถ้า `allow_execution=true` และมี SL
5. ผลเทรด `POST /feedback` → logger / tuner / adaptive block

Engine STOP ที่ EA หรือที่ `/engine` ตัดข้อเสนอใหม่ ดีลที่เปิดแล้วยังให้ EA ดูแล

### 4.2 Server แจกสิทธิ์ (เส้นธุรกิจ)

1. แอดมินออก license จาก EA-Admin / signal API
2. ลูกค้าจ่ายเงิน → subscription ต่ออายุ license
3. Dashboard / บอท Telegram ตรวจ `active && signal_enabled`
4. ลูกค้าได้ ZIP client + คีย์ license
5. EA ตรวจ license ผ่าน header `NT_License.mqh` (ชุด private)

### 4.3 ข่าวและกฎกลาง (เส้นป้องกัน)

- `nexttrade-backend` ดึงปฏิทิน → `/news/guard`
- กฎกลาง `analyze_only`, `max_lot`, หน้าต่างข่าว
- Client agent มี news/guard ของตัวเองบนเครื่อง เพื่อทำงานได้แม้เน็ตฝั่ง server ขาด

สองชั้นกันคนละจุด: server กันทั้งฟลีต, client กันพอร์ตเครื่องนั้น

### 4.4 Multi-agent ฝั่ง server (เส้นสร้าง/รีวิวระบบ)

ใช้ตอนออกแบบ EA หรือรีวิวโค้ด ไม่ได้อยู่ใน tick เทรด

`intent → planner → creator model → reviewer model → risk-agent → usable / blocked`

โมเดล: Claude / ChatGPT / Grok / Gemini  
สิทธิ์เครื่องมือแยก `read_only / write / trade` — ค่าเริ่มไม่มี `trade`

สาย LangGraph บนเครื่องลูกค้าทำกราฟคล้ายกันสำหรับข้อเสนอเทรด (`trade_graph` + `review_graph`)

## 5. สัญญาที่ต้องคงไว้ข้าม repo

| สัญญา | เจ้าของ | ผู้ใช้ |
|---|---|---|
| SNAP 6 บรรทัด → การ์ด BIAS SESSION RISK SETUP | Dashboard `control-layer.js` | หน้าเว็บ |
| HTTP `/health` `/engine` `/propose` `/feedback` | Client `agent.server` | EA WebRequest |
| JSON proposal (`action`, `sl`, `allow_execution`, cards) | `mt5/contract.json` | EA + agent |
| License `active` + `signal_enabled` | Dashboard docs + EA-Admin | บอท / EA |
| Rules JSON (`analyze_only`, caps, news window) | `nexttrade-backend` | MCP / audit |
| Engine START-STOP | Client engine + EA chart button | คนคุมความเสี่ยง |

## 6. ขอบเขตความรับผิดชอบ (กันปน)

| ได้ทำ | ห้ามทำ |
|---|---|
| Dashboard แสดงการ์ด คุมโหมด ตรวจ license | ห้ามมีซอร์ส EA / ห้ามเก็บคีย์ / ห้ามคำนวณล็อตแล้วยิงตลาด |
| Backend สแกน ข่าว กฎ แจ้งเตือน | ห้ามเป็นหน้าเว็บลูกค้า ห้ามแทนที่ client bridge |
| Client agent วิเคราะห์ คำนวณ guard | ห้ามยิงออเดอร์ตรงโบรกเกอร์ |
| EA ยิงออเดอร์ คุมความเสี่ยงฮาร์ด | ห้ามเรียก LLM ตรง ๆ |
| Agent-system รีวิว/วางแผนงาน | ห้ามเป็นชุดติดตั้งลูกค้า |
| LangGraph สายสมองรุ่นใหม่ของ client | ยังไม่แทนที่ dashboard |

## 7. การ deploy ที่ถูกต้องเมื่อรวมระบบ

1. เปิด GitHub Pages จาก `Web-AI-Dashboard-Nexttrade` (public)
2. รัน `nexttrade-backend` บนโฮสต์คุณ พร้อม `ADMIN_TOKEN` และ CORS ชี้ Pages
3. รัน EA-Admin private สำหรับออก/เพิกถอน license
4. ตัด Release จาก `Nexttrade-AI-Agent` (หรือ langgraph เมื่อพร้อม) เป็น ZIP ลูกค้า
5. ลูกค้าติดตั้ง Python + EA ชี้ `127.0.0.1:8787`
6. เริ่มที่โหมด `advise` จนกว่าจะผ่านการทดสอบความเครียด

## 8. สิ่งที่ยังไม่ต่อสายอัตโนมัติ

จุดเหล่านี้มีใน repo แยกแล้ว แต่ยังไม่ใช่ pipeline เดียวที่ล็อกทั้งระบบ

- Dashboard signal-api เป็นโมดูล JS สเปก — ต้องมีโฮสต์ API จริงฝั่ง server
- `nexttrade-agent-system` ยังเป็นชั้น orchestrator ไม่มี HTTP gateway ใน repo
- `Nexttrade-AI-Agent` กับ `-langgraph` เป็นสองสาย client เลือกใช้สายใดสายหนึ่งต่อเครื่อง
- `nexttrade-mc-wfo` อ่านล็อกย้อนหลัง ไม่ได้อยู่ในเส้น `/propose`
- LINE OA อยู่คนละขอบเขต (ซัพพอร์ตคน ไม่ใช่สัญญาณเทรด)

เมื่อต่อสายเพิ่ม ให้แก้เอกสารนี้ชุดเดียวกันทุก repo ไม่แตกสเปกคนละไฟล์
