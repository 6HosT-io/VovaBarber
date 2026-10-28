# VovaBarber (Telegram booking bot)

Bilingual Telegram bot for a **single-barber** shop in Riga.

| | |
|--|--|
| **Address** | Jasmuižas iela 9, Latgales priekšpilsēta, Rīga, LV-1021 |
| **Phone (in confirmations)** | Configurable via `/settings` (default +371 29985759) |
| **Languages** | Russian (primary UI) + Latvian; admin group always Russian |
| **Dates** | DD/MM/YYYY |
| **Server path** | `/opt/VovaBarber` |
| **systemd** | `VovaBarber.service` |
| **Mode** | Long polling |
| **Slot step / duration** | **30 minutes** (overridable in `/settings`) |
| **Timezone** | Europe/Riga |

---

## Client flow

1. **`/book`** → day (Today / Tomorrow / Day after / Other)  
   - Blocked, vacation, or **no free slots** → label **(недоступно)** + alert on tap  
   - **Today**: past times + ~15 min lead are hidden  
2. **Time slots** from Google Calendar **«Клиенты»**  
   - Default window **08:30–21:00** (env or `/settings` → окно слотов)  
   - Step **30 min** by default; order **chronological**  
   - Any event on that calendar (bot or manual) is **busy** — colour does not matter  
3. **Service**  
   - Listed service → **request is sent immediately** (no comment step)  
   - **«Пропустить / свой текст»** → one message with service name (or `-`) → send  
4. Admin group → ✅ / ❌  
   - Client can **«Отозвать заявку»** until barber answers  

Also: prices, history, contact, cancel confirmed, reschedule (same slots → barber must confirm).

**Reminders:** ~24h before + morning of the day (confirm / think / cancel). Morning skipped if client already confirmed on the 24h message. Toggleable in `/settings`.

---

## VIP (experimental)

| Rule | Detail |
|------|--------|
| Who | Numeric Telegram user id only |
| Commands | `/vip_add ID`, `/vip_del ID`, `/vip_list` |
| Busy slots | **⭐** only for VIP; **normals never see stars or occupied times** |
| Closed / vacation days | VIP may still open a day and send a **request for review** |
| Group card | **VIP (исключение)** only when override (busy slot or closed day). Ordinary VIP booking on a free slot looks like a normal request (no clutter) |
| Confirm | Barber still presses ✅ / ❌; no auto-write over someone else’s calendar event |

Telegram inline buttons cannot use real bold/italic/colour. Stars are the VIP marker on the keyboard.

---

## Away banner (vacation / block)

When nearby days are closed (`/vacation`, `/block`, or stored ranges), a short notice can appear on **`/start`** and **`/book`**.

| Command | Effect |
|---------|--------|
| `/away_banner` | Status + current text |
| `/away_banner on` / `off` | Enable / disable |
| `/away_banner ru …` | Custom RU text |
| `/away_banner lv …` | Custom LV text |

Placeholders in custom text: `{start}`, `{end}`, `{reason}`. Day chips still show **(недоступно)** for normal clients.

---

## Accept, decline, suggest other time

| Step | What happens |
|------|----------------|
| **✅ Подтвердить** | Client notified; confirmed booking; event in Calendar at slot time |
| **❌ Отклонить** | Client notified; **pending ticket is kept** (same request) |
| **📅 Предложить другое время** | Barber writes free text (e.g. `14/10/2026 в 11:20`) |
| Client message | **«Барбер предлагает другое время:»** + **Принять** / **Не подходит** |
| **Принять** | Group notified; booking confirmed; **Calendar uses exact HH:MM** (11:20 OK) |
| **Не подходит** | Group: **Предложить ещё** / **Закрыть заявку** |
| **🗑 Закрыть заявку** | Pending removed; client uses `/book` later |

---

## Pending vs confirmed

| State | Storage | Client | Admin |
|-------|---------|--------|-------|
| **Pending / rejected / suggested** | `pending_bookings` | Waiting or considering offer | Group card + **`/pending`** |
| **Confirmed** | `confirmed_bookings` | Active visit | **`/bookings`**, Calendar |
| **Completed** | past dates archived | — | Hidden from `/bookings` |
| **Cancelled** | `cancelled_by_*` | — | Stats |

**`/pending`:** works even if the group message was deleted.  
**`/bookings`:** today + future only (Europe/Riga). Past → `completed`.

---

## Google Calendar «Клиенты»

| Rule | Detail |
|------|--------|
| Bot writes (client) | On ✅ or client accepts a **suggestion** → event at slot / exact suggested time |
| Bot writes (block) | `/block`, `/vacation` → red all-day |
| Bot deletes | Cancel / unblock when event id known |
| Bot reads | Free slots; any event = busy |
| **Calendar → bot sync** | Interval from env or `/settings`: delete → cancel + notify; move → update + notify |
| Manual-only events | Block slots only; do not create bot bookings |

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

## `/settings` (admins)

| Item | Purpose |
|------|---------|
| Цены и услуги | Service list / prices |
| Рабочие часы (текст) | Info text for clients |
| **Окно слотов** | Start / end / step / duration |
| Адрес | In confirmations |
| **Телефон** | In confirmation messages |
| Текст приветствия | `/start` RU/LV |
| **Тексты отпуск / блок** | Client-facing; `{until}` `{date}` |
| Тексты напоминаний | 24h / morning |
| **Напоминания ВКЛ/ВЫКЛ** | Toggle reminder loop |
| **Интервал Calendar sync** | Seconds (min 60) |
| Заблокированные дни | View closed days |
| Показать всё | Summary |

Daily capacity limit UI is removed (Calendar owns capacity).

---

## Admin group behaviour

- Bot does **not** treat normal group chatter or **voice** as client input.  
- **«Имя в контактах»** accepts **text only**.  
- Free-text from clients is forwarded only from **private** chat with the bot.  
- ✅ / ❌ / suggest / close: **ADMIN_IDS only**.

---

## Admin commands (ADMIN_IDS only; silent for others)

| Command | Purpose |
|---------|---------|
| `/admin` `/panel` | Full command list |
| `/settings` | Runtime settings |
| `/pending` | Queue + actions |
| `/bookings [query]` | Today+future confirmed |
| `/week` `/stats` | Week load / funnel |
| `/block` `/unblock` `/vacation` `/unvacation` `/unblock_all` | Close days + Calendar |
| `/vip_add` `/vip_del` `/vip_list` | VIP by Telegram user id |
| `/away_banner` | Away notice on/off + text |
| `/cancel_id` `/edit_id` | Targeted ops |
| `/backup` | Snapshot `runtime_settings.yaml` |
| `/test_group` `/test_calendar` | Diagnostics |

---

## Deploy

```bash
rsync -avz --exclude venv --exclude __pycache__ --exclude .git \
  --exclude config/.env --exclude config/runtime_settings.yaml \
  --exclude config/google_credentials.json \
  ./ root@SERVER_IP:/opt/VovaBarber/

ssh root@SERVER_IP 'systemctl restart VovaBarber'
```

Secrets stay on the server. Unit: **`VovaBarber.service`**.

---

## Changelog (latest)

- **No comment step**: day → time → service → send  
- **VIP experimental**: ⭐ busy slots VIP-only; closed-day requests; `/vip_add|del|list`; group mark only on override  
- **Away banner** on `/start` and `/book`; `/away_banner` toggle and texts  
- Suggest other time after ❌; client Accept / Not suitable; Calendar exact HH:MM  
- `/settings`: slots, phone, vacation/block texts, reminders, sync interval  
- `/bookings` today+future only; Calendar sync loop; day **(недоступно)**  

---

## Partner pin (short)

Клиенты пишут боту; заявки приходят в эту группу.  
Поток: день → время → услуга → сразу заявка (без комментария).  
✅ подтвердить · ❌ отклонить · можно **предложить другое время**.  
VIP (по id): может запросить занятый слот или закрытый день; в карточке «VIP» только если это исключение.  
Очередь: `/pending`. Визиты: `/bookings`. Календарь **Клиенты** = занятость.  
Настройки: `/settings`. Баннер отпуска: `/away_banner`.  
Языки клиента RU/LV; группа на русском.
