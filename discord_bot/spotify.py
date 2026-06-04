"""Резолв Spotify-посилань у назви треків через Spotify Web API.

yt-dlp не грає Spotify напряму, тож ми дістаємо назви ("Виконавець - Трек") і потім
шукаємо їх на YouTube (ytsearch). Авторизація — Client Credentials flow через aiohttp.
"""
import base64
import logging
import re
import time

import aiohttp

from discord_bot import config

log = logging.getLogger("bot.spotify")

# track/playlist/album з open.spotify.com (включно з intl-xx/) або spotify: URI
_SPOTIFY_RE = re.compile(
    r"(?:open\.spotify\.com/(?:intl-[a-z]+/)?|spotify:)(track|playlist|album)[/:]([A-Za-z0-9]+)"
)


def is_spotify_url(text: str) -> bool:
    return "open.spotify.com" in text or text.startswith("spotify:")


def parse_spotify(text: str):
    """(kind, id) або (None, None)."""
    m = _SPOTIFY_RE.search(text)
    return (m.group(1), m.group(2)) if m else (None, None)


def _fmt(track: dict) -> str:
    artists = ", ".join(a.get("name", "") for a in track.get("artists", []))
    name = track.get("name", "")
    return f"{artists} - {name}".strip(" -")


class SpotifyClient:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = None
        self._token_exp = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def _get_token(self, session) -> str:
        if self._token and time.time() < self._token_exp - 30:
            return self._token
        auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        async with session.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {auth}"},
        ) as r:
            r.raise_for_status()
            data = await r.json()
        self._token = data["access_token"]
        self._token_exp = time.time() + data.get("expires_in", 3600)
        return self._token

    async def resolve(self, url: str, limit: int = 500):
        """Повертає (назва_колекції|None, ['Виконавець - Трек', ...])."""
        kind, sid = parse_spotify(url)
        if not kind:
            return None, []

        async with aiohttp.ClientSession() as session:
            token = await self._get_token(session)
            headers = {"Authorization": f"Bearer {token}"}

            if kind == "track":
                async with session.get(
                    f"https://api.spotify.com/v1/tracks/{sid}", headers=headers
                ) as r:
                    r.raise_for_status()
                    t = await r.json()
                return None, [_fmt(t)]

            if kind == "album":
                async with session.get(
                    f"https://api.spotify.com/v1/albums/{sid}", headers=headers
                ) as r:
                    r.raise_for_status()
                    alb = await r.json()
                items = alb.get("tracks", {}).get("items", [])
                return alb.get("name"), [_fmt(t) for t in items][:limit]

            if kind == "playlist":
                names = []
                url_next = (
                    f"https://api.spotify.com/v1/playlists/{sid}"
                    "?fields=name,tracks.items(track(name,artists(name))),tracks.next"
                )
                pl_name = None
                while url_next and len(names) < limit:
                    async with session.get(url_next, headers=headers) as r:
                        r.raise_for_status()
                        data = await r.json()
                    if pl_name is None:
                        pl_name = data.get("name")
                        tracks = data.get("tracks", {})
                    else:
                        tracks = data
                    for it in tracks.get("items", []):
                        tr = it.get("track")
                        if tr:
                            names.append(_fmt(tr))
                    url_next = tracks.get("next")
                return pl_name, names[:limit]

        return None, []


# Глобальний екземпляр
spotify = SpotifyClient(config.SPOTIFY_CLIENT_ID, config.SPOTIFY_CLIENT_SECRET)
