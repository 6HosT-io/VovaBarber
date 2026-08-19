# Google Calendar — пошаговая настройка

После настройки при нажатии **✅ Подтвердить** в группе бот создаёт событие в календаре барбера.

Время берётся из комментария клиента (например «после 16:00»). Если время не найдено — ставится **10:00**. Длительность по умолчанию **45 минут**. Часовой пояс: `Europe/Riga`.

---

## Шаг 1. Google Cloud проект

1. Открой [Google Cloud Console](https://console.cloud.google.com/)
2. Создай проект (например `BarbershopBot`)
3. В меню: **APIs & Services → Library**
4. Найди **Google Calendar API** → **Enable**

---

## Шаг 2. Service Account

1. **APIs & Services → Credentials → Create credentials → Service account**
2. Имя: `barbershop-calendar`
3. Create and continue → роль можно не назначать → Done
4. Открой созданный service account → вкладка **Keys**
5. **Add key → Create new key → JSON**
6. Скачается файл. Переименуй и положи в проект:

```
BarbershopBot/config/google_credentials.json
```

**Не выкладывай этот файл в интернет и не коммить в git.**

В JSON будет поле `client_email` вида:
`barbershop-calendar@PROJECT_ID.iam.gserviceaccount.com`

---

## Шаг 3. Доступ к календарю барбера

1. Открой [Google Calendar](https://calendar.google.com/) под аккаунтом барбера
2. Слева: нужный календарь → **⋮ → Settings and sharing**
3. **Share with specific people** → Add people
4. Вставь `client_email` из JSON
5. Права: **Make changes to events**
6. Send

Скопируй **Calendar ID**:
- Settings → Integrate calendar → Calendar ID  
- Часто это email барбера или `primary` для основного календаря

---

## Шаг 4. .env

В `config/.env` добавь:

```env
GOOGLE_CALENDAR_ID=primary
GOOGLE_CREDENTIALS_FILE=config/google_credentials.json
TIMEZONE=Europe/Riga
```

Если календарь не основной — вставь полный Calendar ID вместо `primary`.

---

## Шаг 5. Зависимости

Уже есть в `requirements.txt`:

```
google-api-python-client
google-auth
google-auth-httplib2
google-auth-oauthlib
```

Если ставил venv раньше:

```bash
pip install google-api-python-client google-auth google-auth-httplib2 google-auth-oauthlib
```

---

## Шаг 6. Проверка

1. Перезапусти бота: `python3 -m src.bot`
2. Сделай тестовую запись: `/book` → день → комментарий с временем, например `16:00 стрижка`
3. В группе нажми **✅ Подтвердить**
4. Под сообщением должно появиться: `📅 Добавлено в Google Calendar`
5. Открой календарь барбера — событие «Barbershop: …»

Если видишь `⚠️ Calendar: не удалось создать событие` — смотри лог в терминале (часто нет share на service account или неверный Calendar ID).

---

## Как это работает

| Момент | Действие |
|--------|----------|
| Клиент отправил заявку | Бот запоминает дату + комментарий |
| Барбер жмёт Подтвердить | Создаётся событие + клиенту уходит подтверждение с адресом |
| Время в комментарии | Парсится (`16:00`, `около 11`, `14.30`) |
| Нет времени в тексте | Старт 10:00 |

---

## Отключение

Удали или закомментируй в `.env` строки `GOOGLE_*` — бот снова будет только подтверждать без календаря.
