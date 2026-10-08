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
| **Mode** | Long polling |
| **Slot step / duration** | **30 minutes** |
| **Timezone** | Europe/Riga |

---

## Client flow

1. **`/book`** → day (Today / Tomorrow / Day after / Other)  
   - Blocked, vacation, or **no free slots** → label **(недоступно)** + alert on tap  
   - **Today**: times already past + ~15 min lead are hidden  
2. **Time slots** from Google Calendar **«Клиенты»**  
   - Window **08:30–21:00** (env)  
   - Step **30 min**; order **chronological** (08:30 → 09:00 → …)  
   - Any event on that calendar (bot or manual) is **busy** — colour does not matter  
3. **Service** (or skip)  
4. Optional free-text comment **or** button **«Отправить без комментария»**  
5. Request → admin group → ✅ / ❌  
   - Under «Заявка отправлена» client sees **«Отозвать заявку»** until barber answers  

Also: prices, history, contact, cancel confirmed, reschedule (same slot flow → barber must confirm).

**Reminders:** ~24h before + morning of the day (buttons: confirm / think / cancel). Morning reminder is skipped if the client already confirmed on the 24h message.

---

## Pending vs confirmed

| State | Storage | Client | Admin |
|-------|---------|--------|-------|
| **Pending** | `pending_bookings` | After send, before ✅ | Group card + **`/pending`** |
| **Confirmed** | `confirmed_bookings` | Active visit | **`/bookings`**, Calendar event |
| **Completed** | same, status `completed` | Past dates auto-archived | Hidden from `/bookings` |
| **Cancelled** | `cancelled_by_*` | Not in active list | Stats |

### `/pending` (admins)

Works even if the group message was deleted.

Per card:

- ✅ Подтвердить / ❌ Отклонить  
- 💬 Написать  
- 🗑 Снять без ответа (remove from queue, no client message)

### Client withdraw (before ✅)

**«Отозвать заявку»** → pending removed, group notified (original card edited when `group_message_id` is stored).

`/cancel` only aborts an **unfinished** wizard (not yet submitted).

---

## `/bookings` (admins)

```text
/bookings              all active (today + future)
/bookings Иван         search name / contact / date / comment
```

- Shows **only today and future** confirmed bookings (Europe/Riga).  
- Dates in the past are marked **completed** on bot start and on each list load — they leave the list and the active count.  
- If none planned → «Активных записей нет.»  
- Cards: name, contact nickname, date, comment, id  
- Buttons: cancel this booking, write to client  
- Pagination + optional bulk cancel  

Cancel via bot also deletes the Calendar event when `calendar_event_id` exists.

---

## History (client)

`/history` or menu **«История записей»**.

- Filled when barber presses ✅ (`service_history`)  
- Cancelled visits are not shown as active history  
- Empty until the first confirmation  

---

## Google Calendar «Клиенты»

| Rule | Detail |
|------|--------|
| Bot writes (client) | On ✅ → event ~30 min from chosen slot |
| Bot writes (block) | `/block`, `/vacation` → red all-day blocks |
| Bot deletes | Cancel / unblock / unvacation when event id known |
| Bot reads | Free slots; **any** event occupies time |
| **Calendar → bot sync** | ~every 3 min (`CALENDAR_SYNC_INTERVAL_SEC`): delete event → cancel + notify client; move time/date → update booking + notify |
| Manual-only events | Affect slots only; do **not** create bot client bookings |

Sync applies to bookings that have `calendar_event_id` (confirmed after Calendar was connected).

Diagnostics: **`/test_calendar`** and **`/test_calendar 02/10/2026`**.

### `.env` (excerpt)

```env
BOT_TOKEN=...
ADMIN_IDS=...
ADMIN_GROUP_ID=...
TIMEZONE=Europe/Riga
CALENDAR_DEFAULT_START=08:30
CALENDAR_DAY_END=21:00
CALENDAR_DEFAULT_DURATION_MIN=30
CALENDAR_SLOT_STEP_MIN=30
CALENDAR_SLOTS_CACHE_TTL=45
CALENDAR_SLOT_LEAD_MIN=15
CALENDAR_SYNC_INTERVAL_SEC=180
GOOGLE_CALENDAR_ID=...@group.calendar.google.com
GOOGLE_CREDENTIALS_FILE=config/google_credentials.json
```

Guide: `docs/Google_Calendar_Setup.md`.

---

## Stats / week (no capacity fraction)

- Old **`0/8`** style load is **removed** (Calendar owns capacity, not a fixed daily limit).  
- Near days and `/week` show a plain count, or hide empty days (`Ближайшие дни: записей нет.`).  
- Capacity limit is disabled for blocking new bookings (`is_day_full` always false).

---

## Admin commands (ADMIN_IDS only; silent for others)

| Command | Purpose |
|---------|---------|
| `/admin` `/settings` | Prices, hours, welcome, reminders |
| `/pending` | Queue + actions without group message |
| `/bookings [query]` | Today+future confirmed |
| `/week` `/stats` | Week load / funnel |
| `/block` `/unblock` `/vacation` `/unvacation` `/unblock_all` | Close days + Calendar |
| `/cancel_id` `/edit_id` | Targeted ops |
| `/backup` | Snapshot `runtime_settings.yaml` |
| `/test_group` `/test_calendar` | Diagnostics |

Group ✅/❌ remain admin-only.

---

## Deploy

```bash
rsync -avz --exclude venv --exclude __pycache__ --exclude .git \
  --exclude config/.env --exclude config/runtime_settings.yaml \
  --exclude config/google_credentials.json \
  ./ root@SERVER_IP:/opt/VovaBarber/

ssh root@SERVER_IP 'systemctl restart VovaBarber'
journalctl -u VovaBarber -n 40 --no-pager
```

Secrets stay on the server only. Unit: **`VovaBarber.service`**.

---

## Changelog (latest)

- Slots **30 min**, **chronological** order; no adjacency chaos in the keyboard  
- Capacity **`n/8` removed** from stats / week / group wording  
- **`/bookings`**: only **today + future**; past → `completed` (Europe/Riga)  
- Google Calendar read/write, `/test_calendar [date]`, block/vacation → Calendar  
- **Calendar sync loop**: manual delete/move → client notification  
- Day **(недоступно)** + smart today (lead time)  
- **Send without comment** + **withdraw pending** before ✅  
- **`/pending`** action buttons if group card is gone  
- Welcome privacy not duplicated when set via `/settings`  
- Reminders 24h + morning; reschedule like book  

---

## Partner pin (short)

Clients book in the bot; requests land in the admin group. Confirm or decline in one tap.  
Pending: `/pending`. Planned visits: `/bookings` (only upcoming).  
What you put in calendar **Клиенты** blocks slots; moving or deleting a bot-created event updates the client.  
Settings: `/settings`. Languages RU/LV for clients; group stays Russian.
