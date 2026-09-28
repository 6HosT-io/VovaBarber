# Google Calendar — подключение к боту (чеклист)

Цель: **один календарь «Barbershop / Clients»**, куда бот пишет клиентов (зелёный) и куда можно ставить «Не работаю» (красный).  
Личный Gmail-календарь и **Family** бот **не** использует.

---

## Зачем отдельный календарь

| Календарь | Бот |
|-----------|-----|
| Основной `имя@gmail.com` | Не подключать — там жизнь, семья, мусор |
| Family | Не подключать |
| **Barbershop / Clients** (новый) | Только его ID в `.env` |

Блоки «не работаю» и клиенты — **в одном** календаре Barbershop, разными цветами. Второй JSON/календарь для блоков не нужен.

---

## Шаг 1. Google Cloud (один раз)

1. [console.cloud.google.com](https://console.cloud.google.com/) → проект (например `BarbershopBot`)
2. **APIs & Services → Library** → **Google Calendar API** → Enable
3. **Credentials → Create credentials → Service account**
   - имя: `barbershop-calendar`
4. Service account → **Keys → Add key → JSON**
5. Файл сохранить как:

```
/opt/VovaBarbershopBot/config/google_credentials.json
```

(локально: `BarbershopBot/config/google_credentials.json`)

В JSON есть `client_email`:  
`barbershop-calendar@….iam.gserviceaccount.com` — **скопируй**.

---

## Шаг 2. Календарь у барбера

Под аккаунтом барбера на [calendar.google.com](https://calendar.google.com/):

1. Слева **+** рядом с «Other calendars» → **Create new calendar**
2. Название: **Barbershop** или **Clients**
3. Create calendar
4. Открой этот календарь → **Settings and sharing**
5. **Share with specific people** → Add the `client_email` from JSON  
   Rights: **Make changes to events**
6. **Integrate calendar** → скопируй **Calendar ID**  
   (длинная строка, часто `…@group.calendar.google.com`)

Цвет календаря в UI можно выбрать зелёным — для удобства глаз.  
События бот всё равно красит: клиент = colorId 10 (зелёный), блок = 11 (красный).

---

## Шаг 3. .env на сервере

```env
GOOGLE_CALENDAR_ID=вставь_Calendar_ID_сюда
GOOGLE_CREDENTIALS_FILE=config/google_credentials.json
TIMEZONE=Europe/Riga
CALENDAR_DEFAULT_START=08:30
CALENDAR_DEFAULT_DURATION_MIN=60
```

```bash
# загрузить json
scp config/google_credentials.json root@SERVER:/opt/VovaBarbershopBot/config/

ssh root@SERVER
chmod 600 /opt/VovaBarbershopBot/config/google_credentials.json
systemctl restart VovaBarbershopBot
```

---

## Шаг 4. Проверка

1. Клиент → `/book` → заявка в группу  
2. Админ → **✅ Подтвердить**  
3. В Google Calendar (календарь **Barbershop**) должно появиться событие:
   - заголовок вида `✂️ Имя — услуга`
   - **зелёный** цвет
   - длительность **60 мин**
   - время из комментария, иначе **08:30**

При отмене записи бот пытается удалить это событие.

---

## Как жить дальше

### Клиенты
- Только через бота → Telegram группа → ✅ → событие в Calendar.  
- Архитектуру кнопок не ломаем.

### «Не работаю» (блок времени)
**Вариант A (руками):** в календаре Barbershop создай событие на нужные часы, название например `🚫 Не работаю`. Лучше красный цвет вручную.  
**Вариант B (бот):** позже команда напишет красный блок через API (`create_block_event`).

`/block` и `/vacation` в боте по-прежнему закрывают **дни в боте**. Связка «бот block → event в Calendar» может быть следующим шагом.

### Слоты по часу (план, не обязательно сегодня)
Бот читает события дня (`list_events_for_day`) → занято = клиент + блоки → свободные окна с **08:30**, шаг **60 мин** → кнопки клиенту.  
Услугу можно убрать из wizard, когда слоты включите.

### VIP / Party Mode
Позже, отдельно от Calendar.

---

## Типичные ошибки

| Симптом | Что проверить |
|---------|----------------|
| Событий нет | Calendar ID, share на service account, JSON path, restart |
| Permission denied | Права **Make changes to events**, не «See only» |
| Пишет не туда | В `.env` не `primary`, а ID календаря **Barbershop** |
| Family виден боту | Не должен: Family не шарь на service account |

---

## Цвета (Google colorId)

| colorId | Смысл у нас |
|---------|-------------|
| 10 | Клиент (зелёный) |
| 11 | Не работаю / блок (красный) |
