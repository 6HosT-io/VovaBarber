# Barbershop Telegram Bot

Bilingual booking bot for a single-barber shop in Riga (Jasmuižas iela 9).  
Languages: Russian (primary) + Latvian.

## What clients can do

- `/start` — welcome + main menu (optional photo from `assets/welcome.png`)
- **Записаться** / `/book` — Today / Tomorrow / Day after / Other date (DD/MM/YYYY) + comment
- **Цены** / `/prices` — service list (editable from admin)
- **История** / `/history` — own bookings (basic)
- **Связаться** / `/contact` — free text goes to the private admin group
- **Отмена** / `/cancel` — cancel current action; group is notified
- Language switch RU ↔ LV

## What the admin group receives

Every booking request, free-text message and cancel request is posted to the private group with:

- Telegram display name
- Contact name (if saved via **Имя в контактах**)
- Day + comment
- Buttons: Confirm / Reject / Write to client / Save contact name

Confirm and Reject also notify the client in private chat.

## Admin commands (only for ADMIN_IDS)

| Command | Purpose |
|---------|---------|
| `/admin` `/panel` | Admin menu |
| `/settings` | Prices, hours, address, welcome texts, reminders, blocked days |
| `/test_group` | Send a test message to the admin group |
| `/block DD/MM/YYYY` | Block one day |
| `/unblock DD/MM/YYYY` | Unblock one day |
| `/vacation DD/MM/YYYY DD/MM/YYYY` | Block a date range |

Date format everywhere: **DD/MM/YYYY** (fixed).

## Settings (`/settings`)

Stored in `config/runtime_settings.yaml` (survives restart):

- Service prices and durations
- Working hours
- Address
- Welcome texts (RU/LV)
- Reminder texts (RU/LV)
- Client contact nicknames (`client_names`)

## BotFather setup

- `/setabouttext` — short bio (≤120 chars)
- `/setdescription` — “What can this bot do?”
- **Edit Description Picture** — 640×360 PNG/JPG (or GIF 320×180 / 640×360 / 960×540)
- **Edit Botpic** — square avatar

## Run

```bash
cd BarbershopBot
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
# fill config/.env: BOT_TOKEN, ADMIN_IDS, ADMIN_GROUP_ID
python3 -m src.bot
```

Optional auto-start on macOS: `launchd` or `pm2` (see project notes).

## Project layout

```
BarbershopBot/
├── assets/welcome.png     # optional /start photo
├── config/
│   ├── .env               # tokens (not in git)
│   ├── services.yaml      # default prices
│   ├── settings.yaml      # default hours, address
│   ├── texts_ru.yaml / texts_lv.yaml
│   └── runtime_settings.yaml  # live overrides
├── src/
│   ├── bot.py
│   ├── handlers/          # common (client) + admin
│   ├── keyboards/
│   └── services/          # settings_store, …
└── requirements.txt
```

## Not in this version yet

- Full reminder scheduler (24h + morning) in production use
- Google Calendar sync
- Persistent booking database / full history
- Telegram Mini App

