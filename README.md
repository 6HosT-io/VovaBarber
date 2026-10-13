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
3. **Service** (or skip)  
4. Optional comment **or** **«Отправить без комментария»**  
5. Request → admin group → ✅ / ❌  
   - Under «Заявка отправлена» client can **«Отозвать заявку»** until barber answers  

Also: prices, history, contact, cancel confirmed, reschedule (same slots → barber must confirm).

**Reminders:** ~24h before + morning of the day (confirm / think / cancel). Morning skipped if client already confirmed on the 24h message. Toggleable in `/settings`.

---

## Accept, decline, suggest other time

| Step | What happens |
|------|----------------|
| **✅ Подтвердить** | Client notified; confirmed booking; event in Calendar at slot time |
| **❌ Отклонить** | Client notified; **pending ticket is kept** (same request) |
| **📅 Предложить другое время** | Barber writes free text (e.g. `14/10/2026 в 11:20`) |
| Client message | **«Барбер предлагает другое время:»** + text + **Принять** / **Не подходит** |
| **Принять** | Group notified; booking confirmed; **Calendar uses exact HH:MM** (11:20 OK, not only :00/:30) |
| **Не подходит** | Group: **Предложить ещё** / **Закрыть заявку**; client may write preferred windows in the bot chat |
| **🗑 Закрыть заявку** | Pending removed; client told to use `/book` later |

Phrase **«Сообщение от барбера»** is not used. Suggest text stays free-form; if `ЧЧ:ММ` and optional `ДД/ММ/ГГГГ` are present, they drive Calendar.

---

## Pending vs confirmed

| State | Storage | Client | Admin |
|-------|---------|--------|-------|
| **Pending / rejected / suggested** | `pending_bookings` | Waiting or considering offer | Group card + **`/pending`** |
| **Confirmed** | `confirmed_bookings` | Active visit | **`/bookings`**, Calendar |
| **Completed** | past dates archived | — | Hidden from `/bookings` |
| **Cancelled** | `cancelled_by_*` | — | Stats |

### `/pending` (admins)

Works even if the group message was deleted. Cards show status (`pending` / `rejected` / `suggested`), optional last suggestion text, and actions (confirm / reject / write / clear).

### Client withdraw (before first decision)

**«Отозвать заявку»** → pending removed, group notified.  
`/cancel` only aborts an unfinished wizard (not yet submitted).

---

## `/bookings` (admins)

```text
/bookings              today + future confirmed
/bookings Иван         search name / contact / date / comment
```

Past dates are marked **completed** (Europe/Riga) and leave the list. Empty → «Активных записей нет.»

---

## History (client)

`/history` — visits after ✅. Cancelled items are not shown as active history.

---

## Google Calendar «Клиенты»

| Rule | Detail |
|------|--------|
| Bot writes (client) | On ✅ or client accepts a **suggestion** → event at slot / exact suggested time |
| Bot writes (block) | `/block`, `/vacation` → red all-day |
| Bot deletes | Cancel / unblock when event id known |
| Bot reads | Free slots; any event = busy |
| **Calendar → bot sync** | ~every 3 min (or interval from `/settings`): delete → cancel + notify; move → update + notify |
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
| **Окно слотов** | Start / end / step / duration (e.g. `08:30 21:00 30 30`) |
| Адрес | In confirmations |
| **Телефон** | In confirmation messages |
| Текст приветствия | `/start` RU/LV |
| **Тексты отпуск / блок** | Client-facing; placeholders `{until}` `{date}` |
| Тексты напоминаний | 24h / morning |
| **Напоминания ВКЛ/ВЫКЛ** | Toggle reminder loop |
| **Интервал Calendar sync** | Seconds (min 60) |
| Заблокированные дни | View closed days |
| Показать всё | Summary |

Daily capacity limit UI is removed (Calendar owns capacity).

---

## Admin group behaviour

- Bot **does not** treat normal group chatter or **voice** as client input.  
- **«Имя в контактах»** accepts **text only** (not voice).  
- Free-text from clients is forwarded only from **private** chat with the bot.  
- ✅ / ❌ / suggest / close: **ADMIN_IDS only**.

---

## Admin commands (ADMIN_IDS only; silent for others)

| Command | Purpose |
|---------|---------|
| `/admin` `/panel` | Full command list |
| `/settings` | Runtime settings (see above) |
| `/pending` | Queue + actions |
| `/bookings [query]` | Today+future confirmed |
| `/week` `/stats` | Week load / funnel |
| `/block` `/unblock` `/vacation` `/unvacation` `/unblock_all` | Close days + Calendar |
| `/cancel_id` `/edit_id` | Targeted ops |
| `/backup` | Snapshot `runtime_settings.yaml` |
| `/test_group` `/test_calendar` | Diagnostics |

---

## Stats / week

No `0/8` capacity fractions. Counts only; empty near days may hide as «записей нет».

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

- **Suggest other time**: after ❌ keep ticket → free-text offer → client Accept / Not suitable → Calendar at **exact HH:MM**  
- Client copy: **«Барбер предлагает другое время:»** (not «Сообщение от барбера»)  
- Close ticket / suggest again after client declines offer  
- `/settings`: slot window, phone, vacation/block texts, reminders toggle, sync interval  
- Slots chronological; capacity `n/8` removed  
- `/bookings` today+future only; past → completed  
- Calendar read/write + sync loop; `/test_calendar [date]`  
- Day **(недоступно)** + smart today  
- Send without comment + withdraw pending  
- `/pending` with actions if group card deleted  
- Group ignores voice for contact-name step  

---

## Partner pin (short)

Клиенты пишут боту; заявки приходят в эту группу.  
✅ подтвердить · ❌ отклонить · при отказе можно **предложить другое время** (клиент жмёт принять / не подходит).  
Очередь: `/pending`. Ближайшие визиты: `/bookings`.  
Календарь **Клиенты** блокирует слоты; точное время из предложения (в т.ч. 11:20) уходит в Calendar после принятия.  
Настройки: `/settings`. Языки клиента RU/LV; группа на русском.
