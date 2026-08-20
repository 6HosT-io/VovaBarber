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
| Prices | **Цены** / `/prices` |
| History | **История** / `/history` — only **active** (not cancelled) visits |
| Contact | **Связаться** / `/contact` — free text → admin group |
| Cancel step | `/cancel` — stops current wizard only |
| Cancel appointment | **❌ Отменить запись** / `/cancel_booking` — cancels confirmed booking (pick if several) |
| Language | **Language / Valoda** — RU ↔ LV |

Public slash menu: `start`, `book`, `prices`, `history`, `contact`, `cancel`, `cancel_booking`, `help`.  
Admin commands are **hidden** from normal users (no reply if they type them).

---

## Admin private group

Every booking request, free-text message and client cancel is posted here.

Shown for each client:

- Telegram name  
- **В контактах** (if saved)  
- **Last time used services** (active history only)  
- Day + comment  

**Buttons on new request**

| Button | Effect |
|--------|--------|
| ✅ Подтвердить | Client gets confirmation + address + phone; booking enters reminders; optional Google Calendar; history updated; button **❌ Отменить эту запись** appears on the group message |
| ❌ Отклонить | Client gets decline (request was never confirmed) |
| 💬 Написать клиенту | Open chat |
| 📝 Имя в контактах | Save barber’s phone nickname for this client |

**After confirm:** group message keeps **❌ Отменить эту запись** for that specific booking.

---

## Cancel rules

| Who | How | Result |
|-----|-----|--------|
| Barber | Group button after confirm, or `/bookings` → cancel, or `/cancel_id ID` | Client notified; history entry removed from “last services”; reminders stopped; Calendar event deleted if any |
| Client | `/cancel_booking` or menu button | Same cleanup; admin group notified |
| Client (several bookings) | Bot shows a list with a cancel button per date | Only the chosen one is cancelled |
| «Нужно перенести» on reminder | Treated as cancel of that slot | Group notified |

Cancelled visits **do not** appear in `/history` or “Last time used services”.

---

## Admin: active bookings

```
/bookings              — all active confirmed appointments
/bookings Саша         — search by Telegram name, contact name, date, comment, id
/cancel_id 1724…       — cancel one booking by ID
```

**List features**

- Pagination: **5** per page, ◀️ ▶️  
- Per card: cancel this booking + write to client  
- **❌ Отменить все на странице** (with confirmation)  
- **❌ Отменить все найденные** (if search was used)  
- **❌ Отменить ВСЕ активные** (with confirmation)  

Bulk cancel notifies each client and cleans history / reminders / Calendar.

---

## Admin commands (ADMIN_IDS only)

| Command | Purpose |
|---------|---------|
| `/admin` `/panel` | Admin menu |
| `/settings` | Prices, hours, address, welcome & reminder texts, blocked days |
| `/test_group` | Test message to the admin group |
| `/bookings` `/active` | Active appointments (+ search) |
| `/cancel_id ID` | Cancel by booking ID |
| `/block DD/MM/YYYY` | Block one day |
| `/unblock DD/MM/YYYY` | Unblock one day |
| `/vacation START END` | Block range (max 90 days) |
| `/unvacation START END` | Unblock range |
| `/unblock_all` | Clear all blocked days |

Examples:

```
/block 25/08/2026
/vacation 01/09/2026 14/09/2026
/unvacation 08/09/2026 14/09/2026
/bookings
/bookings 25/08
/cancel_id 1724123456789
```

---

## Reminders

Run inside the same bot process (started with the service).

| When | Behaviour |
|------|-----------|
| ~24h before | Window **20–28 hours** before appointment time |
| Morning | Same calendar day, after **08:00** Europe/Riga, only if client did **not** press «Да, буду» |

**Buttons on reminder**

- ✅ **Да, буду** — morning reminder skipped  
- 🤔 **Подумаю** — morning reminder still sent  
- 📅 **Нужно перенести** — cancels slot, notifies group  

Time is taken from the client comment (`16:00`, `около 11`, …). Default **10:00** if missing. Duration default **45 min**.  
Texts editable in `/settings`. Timezone: `Europe/Riga`.

---

## Settings (`/settings`)

Stored in `config/runtime_settings.yaml` (survives restart):

- Service prices and durations  
- Working hours  
- Address  
- Welcome texts (RU/LV)  
- Reminder texts (RU/LV)  
- Client contact nicknames (`client_names`)  
- Service history (`service_history`) — cancelled entries marked, not shown  
- Blocked days (`blocked_days`)  
- Pending + confirmed bookings (for confirm / reminders / cancel)  

---

## Google Calendar (optional)

On **Confirm**, bot can create an event. On cancel, it tries to delete it.

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

- **Ubuntu 24.04**, location **Falkenstein (FSN)** or **Helsinki (HEL)**  
- Plan e.g. **CX23** (2 vCPU / 4 GB)  
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

### Firewall

Inbound **TCP 22** (SSH). Later for webhooks: **80**, **443**.  
Hetzner Cloud Firewall and/or UFW.

### Webhooks later

Same VPS: domain + nginx + Let’s Encrypt, then switch bot from long polling to webhook.

---

## BotFather

- `/setabouttext`, `/setdescription`  
- Description picture **640×360**  
- Botpic — square  
- Privacy Policy URL — optional; bot includes a short privacy note on `/start` and `/contact`  

Optional photo: `assets/welcome.png`.

---

## Project layout

```
VovaBarbershopBot/
├── assets/welcome.png
├── config/
│   ├── .env
│   ├── .env.example
│   ├── services.yaml
│   ├── settings.yaml
│   ├── texts_ru.yaml / texts_lv.yaml
│   ├── runtime_settings.yaml
│   └── google_credentials.json      # optional
├── docs/
│   └── Google_Calendar_Setup.md
├── src/
│   ├── bot.py
│   ├── handlers/                    # common + admin
│   ├── keyboards/
│   └── services/                    # settings_store, calendar, reminders
└── requirements.txt
```

---

## Not fully live yet

- Telegram Mini App  

---

## Partner pin (admin group) — short

Clients write to the bot; requests land in this group.  
Confirm / reject / write / save contact name / cancel confirmed booking from the message.  
`/bookings` — list & search & bulk cancel.  
`/block` `/vacation` — close days. Format **DD/MM/YYYY**.  
`/settings` — prices, hours, texts.  
Reminders: 24h + morning; «Да, буду» skips morning.
