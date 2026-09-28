# VovaBarber (Telegram booking bot)

Bilingual Telegram bot for a **single-barber** shop in Riga.

| | |
|--|--|
| **Address** | Jasmuižas iela 9, Latgales priekšpilsēta, Rīga, LV-1021 |
| **Phone (in confirmations)** | +371 29985759 |
| **Languages** | Russian (primary UI) + Latvian; admin group always Russian |
| **Dates** | DD/MM/YYYY |
| **Server path** | `/opt/VovaBarber` |
| **systemd** | `VovaBarber.service` |
| **Mode** | Long polling (webhook-ready later) |

---

## Client flow (current)

1. `/book` → **Today / Tomorrow / Day after / Other date**  
   (blocked & vacation days hidden; **daily capacity limit is off**)
2. **Time slots** from Google Calendar **«Клиенты»**  
   - Window: `CALENDAR_DEFAULT_START` … `CALENDAR_DAY_END` (default **08:30–21:00**)  
   - Step / duration: **30 min** (configurable)  
   - Any event on that calendar (bot **or manual**) occupies time  
   - Slots sorted by **adjacency** (prefer next to existing clients)
3. Choose **service** (or skip)
4. Short **comment** (time already fixed by slot)
5. Request → admin group → ✅ / ❌  

Also: prices, history, contact, cancel, **reschedule** (same slot picker → barber must confirm).

Reminders: ~24h before + morning of the day (buttons; morning skipped if client already confirmed earlier).

---

## Google Calendar «Клиенты»

| Rule | Detail |
|------|--------|
| One calendar | Dedicated calendar ID in `.env` — **not** Family, not personal inbox clutter |
| Bot writes | On ✅ confirm → green-ish event (`✂️`, ~30 min, start from slot) |
| Bot deletes | On cancel when `calendar_event_id` stored |
| Bot reads | **Every** slot offer (with short TTL cache ~45s); pagination via `pageToken` |
| Manual events | Barber adds anything → that interval is **busy** for clients |
| «Не работаю» | Optional label/colour; **any** event blocks the same way |

### `.env` (server)

```env
BOT_TOKEN=...
ADMIN_IDS=1361872676,283788179
ADMIN_GROUP_ID=-100...
GOOGLE_CALENDAR_ID=...@group.calendar.google.com
GOOGLE_CREDENTIALS_FILE=config/google_credentials.json
TIMEZONE=Europe/Riga
CALENDAR_DEFAULT_START=08:30
CALENDAR_DAY_END=21:00
CALENDAR_DEFAULT_DURATION_MIN=30
CALENDAR_SLOT_STEP_MIN=30
CALENDAR_SLOTS_CACHE_TTL=45
```

Setup guide: `docs/Google_Calendar_Setup.md`  
Diagnostics: **`/test_calendar`** (admins) — read calendar + create/delete test event.

Service account email must have **Make changes to events** on calendar «Клиенты».

---

## Adjacency scoring (slot order)

Free starts are generated every step from day start to day end, minus busy intervals from Calendar. Then sorted:

| Priority | Score idea | Meaning |
|----------|------------|---------|
| Exactly **before** a client | +2000 | Slot ends when busy starts |
| Exactly **after** a client | +2000 | Slot starts when busy ends |
| Small hole ≤ duration | +1500 | Fill a one-client gap |
| Near block ≤ 60 min | +800 | Still pack the day |
| Distance penalty | small − | Prefer closer edges |
| Empty day | score 0 | Earlier times first |

Goal: avoid random holes (e.g. finish 15:00, next 17:00) by offering edges first. Barber still confirms in Telegram.

---

## Admin group

Buttons only for **ADMIN_IDS** (alert if someone else taps).

| Button | Effect |
|--------|--------|
| ✅ | Confirm book or reschedule → Calendar event |
| ❌ | Decline; optional suggest another time |
| 💬 / 📝 | Open chat / save “name in contacts” |
| ❌ cancel | After confirm (synced across messages) |

Cancel text differs for client vs barber. Concurrent cancel is locked (RLock + file lock) and idempotent.

---

## Admin commands (ADMIN_IDS only; silent for others)

| Command | Purpose |
|---------|---------|
| `/admin` `/settings` | Prices, hours, welcome, reminders, blocks |
| `/bookings` | Active list + cancel / write client |
| `/pending` | Waiting accept/reject |
| `/week` | Week overview |
| `/stats` | Funnel-style counters |
| `/block` `/unblock` `/vacation` `/unvacation` `/unblock_all` | Bot-side closed days (vacation message differs) |
| `/cancel_id` `/edit_id` | Targeted admin ops |
| `/backup` | Snapshot runtime YAML |
| `/test_group` | Ping group |
| `/test_calendar` | Google Calendar diagnostics |

---

## Deploy / update code

```bash
rsync -avz --exclude venv --exclude __pycache__ --exclude .git \
  --exclude config/.env --exclude config/runtime_settings.yaml \
  --exclude config/google_credentials.json \
  ./ root@SERVER_IP:/opt/VovaBarber/

ssh root@SERVER_IP 'systemctl restart VovaBarber'
journalctl -u VovaBarber -n 40 --no-pager
```

Never commit: `.env`, `google_credentials.json`, `runtime_settings.yaml`.

---

## Security notes (ops)

- **Secrets**: only on server `config/.env` + JSON key; mode `600`; rsync excludes them.
- **Admin**: commands and group callbacks gated by `ADMIN_IDS`.
- **Callbacks**: business actions use `callback_data` + server checks; URL buttons only open chats/links.
- **Group privacy**: prefer BotFather Group Privacy so the bot does not ingest all group chatter.
- **Calendar**: service account limited to the shared «Клиенты» calendar.
- **Token leak**: if BOT_TOKEN ever leaked → revoke in BotFather immediately.
- **Conflict**: only **one** long-polling process (`TelegramConflictError` = second instance).

### Load / concurrency

Designed for a **small shop**, not a ticket flash-sale.

| Scenario | Expectation |
|----------|-------------|
| Normal day (tens of clients) | Fine on CX22-class VPS |
| ~100 clients **spread over time** | OK |
| ~100 **simultaneous** `/book` | Will slow: each slot view hits Calendar (or 45s cache), YAML runtime under lock, single process |

Mitigations if ever needed: longer slot cache, webhook + multi-worker (careful with shared YAML), move runtime to SQLite/Postgres, rate-limit `/book`.

**3–5 s delay on `/book` after choosing a day is normal** when Calendar is cold (TLS + `events.list`). Warm cache (~45s) is faster. Network Riga↔Google dominates, not Telegram itself.

---

## Stack

- Python 3.12 venv, **aiogram 3**, long polling  
- Runtime: YAML (`config/runtime_settings.yaml`) + optional `data/bot.db`  
- Google Calendar API (service account)  
- APScheduler-style reminder loop inside the bot process  

---

## Partner pin (short)

Clients write the bot, not phone. Requests land in the admin group.  
Confirm / decline in one tap. Names + contact nicknames + last visit on the card.  
Times come from calendar slots; what you put in **Клиенты** (including manual and «Не работаю») is busy.  
Settings via `/settings`. Languages RU/LV for clients; group stays Russian.

---

## Changelog (high level)

- Google Calendar read/write, `/test_calendar`, dedicated «Клиенты» calendar  
- Slot-based booking + adjacency packing; capacity-per-day disabled  
- Reschedule uses the same slots  
- Calendar list pagination; short TTL caches for slots & keyboards  
- Admin-only group buttons; cancel/reschedule locking; reminders 24h + morning  
- Deploy path `/opt/VovaBarber`, unit `VovaBarber.service`
