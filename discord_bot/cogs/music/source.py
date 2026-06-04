"""Аудіоджерело yt-dlp -> ffmpeg для відтворення в Discord."""
import asyncio

import discord

from .helpers import _ytdl, make_ffmpeg_options

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get("title", "Невідома назва")
        self.url = data.get("url")
        self.duration = data.get("duration")

    @classmethod
    async def from_url(cls, url, *, loop, filter_str: str | None = None, seek: int | None = None):
        ytdl = _ytdl()

        try:
            data = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False)),
                timeout=20,
            )
        except asyncio.TimeoutError:
            raise RuntimeError("Timeout — трек завантажується занадто довго.")

        if "entries" in data:
            data = data["entries"][0]

        # Шукаємо потік із найвищим бітрейтом серед аудіо (краща якість).
        audio_url = data.get("url")
        if not audio_url:
            best_abr = -1
            for fmt in data.get("formats", []):
                if fmt.get("acodec") not in (None, "none") and fmt.get("url"):
                    abr = fmt.get("abr") or 0
                    if abr > best_abr:
                        best_abr, audio_url = abr, fmt["url"]

        if not audio_url or not audio_url.startswith(("http://", "https://")):
            raise RuntimeError("Не вдалося отримати коректне посилання на аудіо.")

        ffmpeg_opts = make_ffmpeg_options(filter_str=filter_str, seek=seek)
        return cls(discord.FFmpegPCMAudio(audio_url, **ffmpeg_opts), data=data)
