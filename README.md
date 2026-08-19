# VovaBarbershopBot

Bilingual Telegram booking bot for a single-barber shop in Riga  
**Address:** Jasmuižas iela 9, Latgales priekšpilsēta, Rīga, LV-1021  

Languages: **Russian** (primary) + **Latvian**.  
Date format everywhere: **DD/MM/YYYY** (fixed).

---

## What clients can do

| Action | How |
|--------|-----|
| Start | `/start` — welcome text (from `/settings`) + optional `assets/welcome.png` |
| Book | **Записаться** / `/book` — Today / Tomorrow / Day after / Other date + comment |
| Prices | **Цены** / `/prices` — live list from settings |
| History | **История** / `/history` — confirmed visits |
| Contact | **Связаться** / `/contact` — free text → admin group |
| Cancel | `/cancel` or «отменить» — cancels current flow; group is notified |
| Language | **Language / Valoda** — RU ↔ LV |

Slash menu for clients shows only public commands (admin commands are hidden).

---

## Admin private group

Every booking, free-text message and cancel request is posted to the group with:

- Telegram display name  
- **В контактах** (if saved)  
- **Last time used services** (from confirmed history)  
- Day + comment  

**Buttons**

| Button | Effect |
|--------|--------|
| ✅ Подтвердить | Client gets confirmation + address + phone `+371 29985759`; optional Google Calendar event; service saved to history |
| ❌ Отклонить | Client gets polite decline |
| 💬 Написать клиенту | Opens chat with the client |
| 📝 Имя в контактах | Save how the barber knows this person on the phone |

---

## Admin commands (ADMIN_IDS only)

Non-admins get **no response** and do not see these in the `/` menu.

| Command | Purpose |
|---------|---------|
| `/admin` `/panel` | Admin menu |
| `/settings` | Prices, hours, address, welcome & reminder texts, blocked days |
| `/test_group` | Test message to the admin group |
| `/block DD/MM/YYYY` | Block one day |
| `/unblock DD/MM/YYYY` | Unblock one day |
| `/vacation START END` | Block date range (max 90 days) |
| `/unvacation START END` | Remove block from a range |
| `/unblock_all` | Clear all blocked days |

Examples:

```
/block 25/08/2026
/vacation 01/09/2026 14/09/2026
/unvacation 08/09/2026 14/09/2026
/unblock_all
```

---

## Settings (`/settings`)

Stored in `config/runtime_settings.yaml` (survives restart):

- Service prices and durations  
- Working hours  
- Address  
- Welcome texts (RU/LV) — used on `/start`  
- Reminder texts (RU/LV)  
- Client contact nicknames (`client_names`)  
- Service history (`service_history`)  
- Blocked days (`blocked_days`)  
- Pending bookings (for confirm → calendar)

---

## Google Calendar (optional)

When admin presses **Confirm**, the bot can create an event.

Guide: `docs/Google_Calendar_Setup.md`

```env
GOOGLE_CALENDAR_ID=primary
GOOGLE_CREDENTIALS_FILE=config/google_credentials.json
TIMEZONE=Europe/Riga
```

Time is parsed from the client comment (`16:00`, `около 11`, …). Default start **10:00**, duration **45 min**.

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

Recommended: **Ubuntu 24.04**, location **Falkenstein (FSN)** or **Helsinki (HEL)**, plan **CX23** (2 vCPU / 4 GB) or similar.

Server path: `/opt/VovaBarbershopBot`  
Systemd unit: **`VovaBarbershopBot.service`**

### Useful commands on server

```bash
systemctl status VovaBarbershopBot
systemctl restart VovaBarbershopBot
systemctl stop VovaBarbershopBot
journalctl -u VovaBarbershopBot -f
```

### Deploy code from Mac

```bash
rsync -avz --exclude venv --exclude __pycache__ --exclude .git \
  --exclude config/.env --exclude config/runtime_settings.yaml \
  ./ root@SERVER_IP:/opt/VovaBarbershopBot/

ssh root@SERVER_IP 'systemctl restart VovaBarbershopBot'
```

### Firewall

Open inbound **TCP 22** (SSH). Later for webhooks: **80** and **443**.  
Hetzner Cloud Firewall and/or UFW on the server.

### Webhooks later

Same VPS works: add domain → nginx + Let’s Encrypt → switch bot from long polling to webhook. No need to change host.

### Python on server

Install **3.12** (deadsnakes PPA if needed). Do not use system 3.14 for the venv.

---

## BotFather

- `/setabouttext` — short bio (≤120 chars)  
- `/setdescription` — longer description  
- Description picture — **640×360** PNG/JPG  
- Botpic — square avatar  

Optional in-bot photo: `assets/welcome.png` (640×360).

---

## Project layout

```
VovaBarbershopBot/
├── assets/welcome.png
├── config/
│   ├── .env                      # secrets (not for public git)
│   ├── .env.example
│   ├── services.yaml             # default prices
│   ├── settings.yaml             # default hours, address
│   ├── texts_ru.yaml / texts_lv.yaml
│   ├── runtime_settings.yaml     # live overrides + history
│   └── google_credentials.json   # optional Calendar key
├── docs/
│   └── Google_Calendar_Setup.md
├── src/
│   ├── bot.py
│   ├── handlers/                 # common (client) + admin
│   ├── keyboards/
│   └── services/                 # settings_store, calendar
└── requirements.txt
```

---

## Not fully live yet

- Automatic 24h / morning reminder scheduler in production  
- Telegram Mini App  

---

## Partner pin text (admin group)

See project chat notes: short RU guide for the barber covering group notifications, buttons, block/vacation commands, and `/settings`.
