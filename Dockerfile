# Образ Discord-бота для незалежного always-on (будь-який Linux/VPS).
# Збірка:   docker build -t discord-bot .
# Запуск:   див. docker-compose.yml (рекомендовано) або deploy/DOCKER.md
FROM python:3.13-slim

# ffmpeg обов'язковий для відтворення аудіо (yt-dlp -> ffmpeg)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Спершу залежності — кешується окремо від коду
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код бота (секрети та runtime-дані НЕ копіюємо — див. .dockerignore)
COPY discord_bot/ ./discord_bot/
COPY run_bot.py .

# Небуферизований UTF-8 вивід -> читабельні логи в `docker logs`
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

# Дані (favorites/playlists/guild_settings/status/log/lock) персистяться через том
VOLUME ["/app/discord_bot/data"]

CMD ["python", "run_bot.py"]
