# Docker / VPS — незалежний always-on

Запуск бота в контейнері, щоб він працював 24/7 **незалежно від твого ПК** (на VPS або
будь-якій машині з Docker). На відміну від `run_24_7.bat`, не потребує входу в Windows.

Файли в корені проєкту: `Dockerfile`, `.dockerignore`, `docker-compose.yml`.
Образ містить **ffmpeg** і всі залежності; секрети та дані в образ НЕ зашиті.

## Локально (перевірити, що працює)

```bash
# у корені проєкту, поряд має лежати заповнений .env
docker compose up -d --build      # зібрати й стартувати у фоні
docker compose logs -f            # дивитися логи (Ctrl+C — вийти з перегляду)
docker compose down               # зупинити
```

> Windows: спершу запусти **Docker Desktop** (інакше `error during connect ... pipe`).

## Деплой на VPS (Ubuntu/Debian)

```bash
# 1. На VPS встанови Docker (один раз)
curl -fsSL https://get.docker.com | sh

# 2. Залий код (git clone приватного репо або scp). Приклад:
git clone https://github.com/Zonda001/DiscordBot.git && cd DiscordBot

# 3. Створи .env (скопіюй з .env.example і впиши DISCORD_BOT_TOKEN тощо)
cp .env.example .env && nano .env

# 4. Старт
docker compose up -d --build
```

Готово — `restart: unless-stopped` підніме бота після падіння й після ребуту VPS.

## Що персиститься

Том `./discord_bot/data` → `/app/discord_bot/data`: обране, плейлисти, пер-серверні
налаштування, статус і ротований `bot.log`. Контейнер можна перебудовувати — дані лишаються.

## Оновлення версії

```bash
git pull
docker compose up -d --build      # перезбере образ і перезапустить
```

## cookies для yt-dlp (опційно)

Якщо використовуєш `cookies.txt` — поклади його в корінь і розкоментуй у `docker-compose.yml`:

```yaml
      - ./cookies.txt:/app/cookies.txt:ro
```

## Веб-дашборд у контейнері

За замовчуванням дашборд слухає `127.0.0.1` — **усередині контейнера**, тобто ззовні
недоступний. Щоб відкрити:

1. У `.env`: `DASHBOARD_HOST=0.0.0.0` і `DASHBOARD_PASSWORD=<надійний пароль>`.
2. У `docker-compose.yml` розкоментуй проброс порту:
   ```yaml
       ports:
         - "127.0.0.1:8765:8765"
   ```
3. ⚠️ **Не виставляй порт у публічний інтернет напряму.** Для віддаленого доступу —
   SSH-тунель (`ssh -L 8765:127.0.0.1:8765 user@vps`) або реверс-проксі з HTTPS
   (Caddy/nginx) + той самий пароль.

## Корисне

```bash
docker compose ps                 # статус
docker compose logs --tail=100    # останні логи
docker compose restart            # перезапуск
docker stats discord-bot          # CPU/RAM
```
