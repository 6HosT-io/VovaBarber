# VovaBarbershopBot

Bilingual Telegram booking bot for a single-barber shop in Riga.  
**Address:** Jasmuižas iela 9, Latgales priekšpilsēta, Rīga, LV-1021  
**Phone (in confirmations):** +371 29985759  

Languages: **Russian** (primary) + **Latvian**.  
Date format everywhere: **DD/MM/YYYY** (fixed).

---

## What clients can do

| Action | How |
|--------|-----|
| Start | `/start` — welcome (from `/settings` or built-in) + privacy note + optional `assets/welcome.png` |
| Book | **Записаться** / `/book` — Today / Tomorrow / Day after / Other date + comment |
| Reschedule | **📅 Перенести запись** / `/reschedule` — request goes to group for barber **accept / reject** (old booking stays until accepted) |
| Prices | **Цены** / `/prices` |
| History | **История** / `/history` — active visits only, **paginated** (5 per page) |
| Contact | **Связаться** / `/contact` — free text → admin group (private chats only; group messages are ignored) |
| Cancel step | `/cancel` — stops current wizard only |
| Cancel appointment | **❌ Отменить запись** / `/cancel_booking` — confirmed booking (pick if several) |
| Language | **Language / Valoda** — RU ↔ LV |

Public slash menu includes: `start`, `book`, `prices`, `history`, `contact`, `cancel`, `cancel_booking`, `reschedule`, `help`.  
Admin commands are **hidden** from normal users (no reply).

Closed days and full days: client gets a clear message (see **Block vs vacation** and **Daily capacity** below) and cannot complete a request for that date.

---

## Admin private group

Every booking request, reschedule request, free-text message and client cancel is posted here.

Shown for each client:

- Telegram name  
- **В контактах** (if saved)  
- **Last time used services** — **one** relevant past visit (closest on or before the request date, with “N days ago” when possible)  
- Day + comment  

**Buttons on new request / reschedule**

| Button | Effect |
|--------|--------|
| ✅ Подтвердить / Подтвердить перенос | Client notified; reminders; optional Google Calendar; history updated; **❌ Отменить эту запись** on the group message |
| ❌ Отклонить | New booking declined; for **reschedule** — old booking **stays** |
| 💬 Написать клиенту | Open chat |
| 📝 Имя в контактах | Save barber’s phone nickname |

**Access control (ADMIN_IDS only)**

All admin actions are restricted to Telegram user IDs listed in `ADMIN_IDS` (you + barber). Non-admins get an alert (buttons) or **no reply** (commands).

| Surface | What is locked |
|---------|----------------|
| Group booking card | ✅ Confirm, ❌ Reject, ❌ Cancel booking, 📝 Contact name |
| Group reschedule card | ✅ Confirm reschedule, ❌ Reject, 📝 Contact name |
| `/bookings` cards & bulk | Cancel one, cancel page, cancel all, pagination |
| `/settings` & panel buttons | Prices, hours, welcome, reminders, capacity, blocked days |
| Commands | `/admin`, `/settings`, `/bookings`, `/block`, `/vacation`, `/stats`, `/cancel_id`, `/test_group`, … |

Telegram still *shows* inline buttons to every group member; the bot **ignores** presses from non-admins. Commands typed by non-admins produce **no response**.

`ADMIN_IDS` example: `1361872676,283788179`

Group Privacy (BotFather): enable so normal chat in the admin group is **not** re-forwarded by the bot. Free-text handler only runs in **private** client chats.

---

## Cancel rules (idempotent)

| Who | How | Result |
|-----|-----|--------|
| Barber | Group button, `/bookings`, or `/cancel_id ID` | Client gets “Барбер отменил…”; history cleaned; reminders stop; Calendar event removed if any |
| Client | `/cancel_booking` or menu button | Client gets “Вы отменили…”; group notified |
| Second cancel of same booking | Any path | **No** second client notify; alert “Уже отменено” / “Клиент уже отменил”; buttons stripped |

Cancel is locked in store (threading + file lock). Status is the source of truth; extra UI buttons on old messages do not re-cancel.

---

## Reschedule (= same flow as book)

1. Client chooses booking → new day → comment  
2. Group gets **Запрос на перенос** (old date → new date)  
3. Barber **confirms** or **rejects**  
4. Until then, the **old** appointment remains active  

---

## Block vs vacation (different client texts)

| Command | Stored as | Client message |
|---------|-----------|----------------|
| `/block DD/MM/YYYY` | simple **block** | Short: day unavailable, pick another |
| `/vacation START END` | **vacation** range | Friendly: on break until **last vacation day**, can book **after** that date |
| `/unblock` / `/unvacation` / `/unblock_all` | open days again | — |

Vacation is stored both as day tags and as `vacation_ranges` (so the client always gets the “on break until …” text).  
After deploying this logic, **run `/vacation` again** for the current holiday — older closes may still be tagged only as simple block.

Examples:

```
/block 25/09/2026
/vacation 06/09/2026 21/09/2026
/unvacation 15/09/2026 21/09/2026
/unblock_all
```

---

## Daily capacity (anti-overload)

Configurable without code changes:

- `/settings` → **📊 Лимит заявок/день** (default **8**)  
- Counts **confirmed** + **pending** requests for that calendar date  
- When full → client cannot select that day (capacity message)

Use this so “tomorrow” cannot collect 30 open requests for a solo barber.

---

## Admin: active bookings

```
/bookings              — all active confirmed appointments
/bookings Саша         — search by name, contact, date, comment, id
/cancel_id 1724…       — cancel by ID
```

- Pagination: **5** per page  
- Per card: cancel + write to client  
- Bulk: cancel page / all found / all active (with confirmation)  

---

## Admin commands (ADMIN_IDS only)

| Command | Purpose |
|---------|---------|
| `/admin` `/panel` | Admin menu |
| `/settings` | Prices, hours, address, welcome & reminder texts, blocked days, **daily capacity** |
| `/test_group` | Test message to admin group |
| `/bookings` `/active` | Active appointments (+ search, pagination, bulk cancel) |
| `/cancel_id ID` | Cancel by booking ID |
| `/stats` | Usage counters (starts, requests, confirms, cancels, reschedules) |
| `/block` `/unblock` | One day (simple block) |
| `/vacation` `/unvacation` | Date range (vacation reason) |
| `/unblock_all` | Clear all closed days |

---

## Reminders

| When | Behaviour |
|------|-----------|
| ~24h before | Window **20–28 hours** before appointment time |
| Morning | Same day after **08:00** Europe/Riga, only if client did **not** press «Да, буду» |

Buttons: ✅ Да, буду · 🤔 Подумаю · 📅 Нужно перенести (starts reschedule flow).  
Texts editable in `/settings`. Timezone: `Europe/Riga`.

---

## Settings (`/settings`) → `config/runtime_settings.yaml`

- Service prices and durations  
- Working hours, address  
- Welcome & reminder texts (RU/LV)  
- Client contact nicknames  
- Service history (cancelled hidden from “last services” and client history)  
- Closed days + reasons (`block` / `vacation`)  
- **max_bookings_per_day**  
- Pending + confirmed bookings  
- Simple **stats** counters  

---

## Google Calendar (optional)

On confirm: create event. On cancel: try delete.  
Guide: `docs/Google_Calendar_Setup.md`

```env
GOOGLE_CALENDAR_ID=primary
GOOGLE_CREDENTIALS_FILE=config/google_credentials.json
TIMEZONE=Europe/Riga
```

---

## Config (`.env`)

```env
BOT_TOKEN=...
ADMIN_IDS=123456789
ADMIN_GROUP_ID=-100xxxxxxxxxx
DATABASE_PATH=data/bot.db
TIMEZONE=Europe/Riga

# Optional
# GOOGLE_CALENDAR_ID=primary
# GOOGLE_CREDENTIALS_FILE=config/google_credentials.json
# NOTIFY_DELAY_SEC=0.35
```

---

## Local run

Use **Python 3.12** (3.14 breaks `pydantic-core`).

```bash
cd VovaBarbershopBot
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# fill config/.env
python -m src.bot
```

---

## Production: Hetzner Cloud

- **Ubuntu 24.04**, Falkenstein (FSN) or Helsinki (HEL)  
- Path: `/opt/VovaBarbershopBot`  
- Unit: **`VovaBarbershopBot.service`**  
- Python **3.12** in venv  

```bash
systemctl status VovaBarbershopBot
systemctl restart VovaBarbershopBot
journalctl -u VovaBarbershopBot -f
```

### Deploy from Mac

```bash
rsync -avz --exclude venv --exclude __pycache__ --exclude .git \
  --exclude config/.env --exclude config/runtime_settings.yaml \
  ./ root@SERVER_IP:/opt/VovaBarbershopBot/

ssh root@SERVER_IP 'systemctl restart VovaBarbershopBot'
```

Do **not** overwrite `runtime_settings.yaml` on deploy (prices, blocks, history, capacity live there).

### Firewall / webhooks later

Inbound **22** (SSH); later **80/443** for HTTPS webhook on the same VPS.

---

## BotFather

- About / description / 640×360 picture / botpic  
- **Group Privacy = Enable** (recommended) so admin group chat is not treated as client free-text  
- Privacy Policy URL optional; short note already on `/start` and `/contact`  

---

## Project layout

```
VovaBarbershopBot/
├── assets/welcome.png
├── config/
│   ├── .env / .env.example
│   ├── services.yaml, settings.yaml, texts_*.yaml
│   ├── runtime_settings.yaml      # live data — keep on server
│   └── google_credentials.json    # optional
├── docs/Google_Calendar_Setup.md
├── src/
│   ├── bot.py
│   ├── handlers/                  # common + admin
│   ├── keyboards/
│   └── services/                  # settings_store, calendar, reminders
└── requirements.txt
```

---

## Not fully live yet

- Telegram Mini App  
- Per-hour time slots (capacity is **per calendar day**)  

---

## Partner pin (admin group) — short

Клиенты пишут боту; заявки и переносы приходят сюда.  
✅ / ❌ / написать / имя в контактах / отмена после подтверждения.  
`/bookings` — список, поиск, пагинация, массовая отмена.  
`/block` — день закрыт (короткий ответ клиенту).  
`/vacation` — отпуск (текст про отдых до конечной даты).  
`/settings` — цены, часы, лимит заявок на день.  
Формат дат: **ДД/ММ/ГГГГ**.  
`/stats` — сколько стартов и заявок.
