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
   - Blocked or vacation → **(недоступно)** + alert on tap  
   - **Today**: past times + ~15 min lead are hidden; only **today** hits Calendar on the day keyboard (faster UX)  
2. **Time slots** from Google Calendar **«Клиенты»**  
   - Default window **08:30–21:00** (env or `/settings`)  
   - Step **30 min**; chronological order  
   - Any event on that calendar (bot or manual) is **busy**  
3. **Service**  
   - Listed service → **request sent immediately** (no comment step)  
   - **«Пропустить / свой текст»** → one message with service name (or `-`) → send  
4. Admin group → ✅ / ❌  
   - Client can **«Отозвать заявку»** until barber answers  

**`/help`** (public): short how-to + commands (RU/LV).

Also: prices, history, contact, cancel confirmed, reschedule (same slots → barber confirms).

**Reminders:** ~24h before + morning of the day (confirm / think / cancel). Morning skipped if client already confirmed on the 24h message. Toggle in `/settings`.

---

## VIP (experimental)

| Rule | Detail |
|------|--------|
| Who | Numeric Telegram user id only |
| Commands | `/vip_add ID`, `/vip_del ID`, `/vip_list` |
| Busy slots | **⭐** only for VIP; **normals never see stars or occupied times** |
| Closed / vacation days | VIP may open a day and send a **request for review** |
| Group card | **VIP (исключение)** only on override (busy slot or closed day). Free-slot VIP visits look normal |
| Confirm | Barber still presses ✅ / ❌; no auto-overwrite of another client’s Calendar event |

Telegram inline buttons do not support real bold/italic/colour. Stars are the VIP marker on the keyboard.

---

## Away banner (vacation / block)

When nearby days are closed (`/vacation`, `/block`, or stored ranges), a short notice can appear on **`/start`** and **`/book`**.

| Control | Effect |
|---------|--------|
| `/away_banner` | Status + buttons Вкл/Выкл |
| `/away_banner on` / `off` | Enable / disable |
| `/away_banner ru …` / `lv …` | Custom text |
| `/settings` → **Баннер отпуска: ВКЛ/ВЫКЛ** | Same toggle |
| `/settings` → **Текст баннера отпуска** | RU/LV text editor |

Placeholders: `{start}`, `{end}`, `{reason}`. Day chips still show **(недоступно)** for normal clients.

---

## Accept, decline, suggest other time

| Step | What happens |
|------|----------------|
| **✅ Подтвердить** | Client notified; confirmed booking; Calendar event at slot time |
| **❌ Отклонить** | Client notified; **pending ticket kept** |
| **📅 Предложить другое время** | Barber free text (e.g. `14/10/2026 в 11:20`) |
| Client | **«Барбер предлагает другое время:»** + **Принять** / **Не подходит** |
| **Принять** | Group notified; confirmed; Calendar at **exact HH:MM** |
| **Не подходит** | Group: **Предложить ещё** / **Закрыть заявку** |
| **🗑 Закрыть заявку** | Pending removed |

---

## Pending vs confirmed

| State | Storage | Admin |
|-------|---------|--------|
| Pending / rejected / suggested | `pending_bookings` | Group card + **`/pending`** |
| Confirmed | `confirmed_bookings` | **`/bookings`**, Calendar |
| Completed | past dates archived | Hidden from `/bookings` |
| Cancelled | `cancelled_by_*` | Stats |

**`/pending`:** works even if the group message was deleted.  
**`/bookings`:** today + future only (Europe/Riga).

---

## Google Calendar «Клиенты»

| Rule | Detail |
|------|--------|
| Bot writes (client) | On ✅ or client accepts a suggestion |
| Bot writes (block) | `/block`, `/vacation` → red all-day |
| Bot reads | Free slots; any event = busy |
| **Calendar → bot sync** | Interval from env/`settings`; delete → cancel + notify; move → update + notify |

Diagnostics: **`/test_calendar`**, **`/test_calendar DD/MM/YYYY`**.

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
| **Окно слотов** | Start / end / step / duration (`08:30 21:00 30 30`) |
| Адрес | In confirmations |
| **Телефон** | In confirmation messages |
| Текст приветствия | `/start` RU/LV |
| **Тексты отпуск / блок** | Message when client taps a closed day; `{until}` `{date}` |
| **Баннер отпуска: ВКЛ/ВЫКЛ** | Notice on `/start` and `/book` when nearby days are closed |
| **Текст баннера отпуска** | Custom RU/LV; `{start}` `{end}` `{reason}` |
| Тексты напоминаний | 24h / morning |
| **Напоминания ВКЛ/ВЫКЛ** | Toggle reminder loop |
| **Интервал Calendar sync** | Seconds (min 60) |
| Заблокированные дни | View closed days |
| Показать всё | Summary |

VIP is **not** in `/settings` (commands: `/vip_add` `/vip_del` `/vip_list`).  
Daily capacity limit UI is removed (Calendar owns capacity).

---

## Admin group behaviour

- Bot ignores normal group chatter and **voice** as client input.  
- **«Имя в контактах»** accepts **text only**.  
- Client free-text is forwarded only from **private** chat with the bot.  
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
| `/away_banner` | Away notice on/off + text + buttons |
| `/cancel_id` `/edit_id` | Targeted ops |
| `/backup` | Snapshot `runtime_settings.yaml` |
| `/test_group` `/test_calendar` | Diagnostics |
| `/ping` | Bot + Calendar API latency |
| `/status` | Long polling uptime, last update, reminder/sync ticks |

---

## Latency and health

| Cause | What happens |
|-------|----------------|
| Google Calendar | Slot list and (formerly) multi-day probe; cold API often **2–5 s** |
| Day keyboard now | Only **today** calls Calendar; tomorrow / day-after open until picked |
| Slot cache | ~**45 s** (`CALENDAR_SLOTS_CACHE_TTL`) |
| Long polling | Idle with no clients is normal; process must stay up |

**`/ping`:** process OK + Calendar API ms for today without cache.  
**`/status`:** mode `long_polling`, process uptime, last Telegram update type/age, last reminder tick, last calendar-sync tick, pending/confirmed counts.

Server checks:

```bash
systemctl status VovaBarber
journalctl -u VovaBarber -n 50 --no-pager
# optional: needrestart -b  → KSTA:1 means no kernel reboot required
```

`systemctl restart VovaBarber` restarts **only the bot process**, not the whole VPS.

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

Secrets stay on the server. Unit: **`VovaBarber.service`**.

---

## Changelog (latest)

- **`/help`** for clients (how-to + commands RU/LV)  
- **`/ping`** + **`/status`**: latency and long-polling / background-loop health  
- Faster day keyboard (Calendar probe only for today)  
- **No comment step**: day → time → service → send  
- **VIP experimental**: ⭐ busy slots VIP-only; closed-day requests; group mark only on override  
- **Away banner** on `/start`/`/book`; `/away_banner` + `/settings` toggle and texts  
- Suggest other time after ❌; Calendar exact HH:MM  
- `/settings`: slots, phone, vacation/block texts, reminders, sync interval  

---

## Partner pin (short)

Клиенты пишут боту; заявки приходят в эту группу.  
Поток: день → время → услуга → сразу заявка (без комментария).  
✅ подтвердить · ❌ отклонить · можно **предложить другое время**.  
VIP (по id): занятый слот или закрытый день — в карточке «VIP» только как исключение.  
Очередь: `/pending`. Визиты: `/bookings`. Календарь **Клиенты** = занятость.  
Настройки: `/settings`. Баннер отпуска: `/away_banner`.  
Проверка бота: `/ping`, `/status`. Справка для клиентов: `/help`.  
Языки клиента RU/LV; группа на русском.
