# CLAUDE.md

Гайд для роботи з цим репозиторієм (для Claude Code та розробників).

## Що це

Об'єднаний Discord-бот (`discord_bot/`) на `discord.py` 2.x: музика, модерація
(кікер), керування нікнеймами, довідка. Зібраний з трьох старих скриптів. Деплой 24/7
на Windows (див. `deploy/`). Окремо лежать **непов'язані** Minecraft-утиліти в корені
(`KolyaBeta.py`, `MinecraftAutoCmd_GUI.py`, `Mine.py`, `build_GUI_exe.py`) — їх не чіпати
без потреби.

## Структура

```
discord_bot/
  main.py          точка входу: CombinedBot, логування(ротація), single-instance lock,
                   динамічний префікс, валідація, _sync_slash, on_command_error
  config.py        завантаження .env, validate(), _int_env()
  settings.py      GuildSettingsStore (пер-серверні налаштування) + singleton `settings`
  cogs/
    music.py       плеєр, черга, фільтри, lyrics, обране, View-кнопки, DJ-роль/vote-skip
    moderation.py  кікер (targets у data/targets.json)
    admin.py       нікнейми
    help.py        hybrid /help ембедом
    status.py      пише data/status.json для desktop-панелі
    dashboard.py   aiohttp веб-дашборд у процесі бота (вмик. через DASHBOARD_PASSWORD)
  spotify.py       резолв Spotify-посилань (aiohttp, client-credentials; з 11.02.2026
                   ключі Web API лише для Premium-акаунтів)
  playlists.py     PlaylistStore (іменовані плейлисти, per-user)
  data/            runtime JSON (favorites, targets, guild_settings, status, playlists),
                   bot.log, bot.lock — gitignored
run_bot.py         зручний запуск: python run_bot.py
panel/             desktop-панель (app.py): супервізор бота + лог + статус + .env
deploy/            run_24_7.bat + install/uninstall (startup-ярлик / панель / Task Scheduler)
tests/             pytest-набір
```

## Запуск

```bash
pip install -r requirements.txt
# .env у корені (скопіювати з .env.example), вписати DISCORD_BOT_TOKEN
python run_bot.py
```
Потрібен **ffmpeg** у PATH. Privileged Intents у Developer Portal: Server Members +
Message Content.

## Тести

```bash
python -m pytest -q
```
Тести не ходять у мережу й не потребують підключення до Discord (завантаження cogs ≠
конект). Конфіг — `pytest.ini` (`asyncio_mode=auto`, `pythonpath=.`).

## Патерни (дотримуватись для послідовності)

- **Команди — гібридні**: `@commands.hybrid_command(...)` → працюють як `!cmd` і `/cmd`.
  Slash синхронізується по гільдіях у `_sync_slash` (on_ready). Перша лінія відповіді на
  довгу команду — `await ctx.defer()` (див. `play`).
- **JSON-сховища** — однаковий патерн: клас із `_load/_save/get/set|add/remove`, файл у
  `config.DATA_DIR`. Приклади: `FavoritesStore` (music.py), `targets` (moderation.py),
  `GuildSettingsStore` (settings.py). Нові дані — так само. Якщо даних побільшає —
  розглянути SQLite за тією ж абстракцією.
- **Пер-серверні налаштування** — через `from discord_bot.settings import settings`:
  `settings.get(guild_id, "autoplay")`, `settings.set(...)`. Дефолти в `DEFAULTS`.
- **UI** — `discord.ui.View` з `on_timeout`, що вимикає кнопки. Приклади: `QueueView`,
  `NowPlayingView` (music.py). Створювати View лише в async-контексті (потрібен loop).
- **Логування** — `logging.getLogger("bot.<area>")`; не `print`. Файл ротується сам.
- **Кирилиця** — повідомлення українською; у консольних тестах ставити
  `PYTHONIOENCODING=utf-8` (cp1251 не виводить емодзі/кирилицю, але це лише консоль).

## Деплой 24/7 (Windows)

`deploy/run_24_7.bat` крутить бота в циклі (рестарт при падінні); логи пише сам Python у
`discord_bot/data/bot.log` (ротований). Автозапуск: `deploy/install_startup.ps1`
(без адміна, startup-ярлик) або `deploy/install_task.ps1` (Task Scheduler, потрібен
адмін). Single-instance lock не дає двох інстансів.

## Безпека

Секрети лише в `.env` (gitignored). НІКОЛИ не комітити токени. `.env.example` — без
реальних значень.
