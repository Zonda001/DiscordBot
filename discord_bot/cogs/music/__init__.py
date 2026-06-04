"""Музичний cog (підпакет). Публічний API + точка входу setup()."""
from .helpers import (
    AUDIO_FILTERS,
    build_nowplaying_embed,
    build_queue_embed,
    fmt_time,
    make_ffmpeg_options,
    member_is_dj,
    progress_bar,
    votes_needed,
    _youtube_id,
)
from .stores import FavoritesStore
from .source import YTDLSource
from .player import MusicPlayer
from .views import NowPlayingView, QueueView, SearchSelectView
from .cog import MusicCog, setup

__all__ = [
    "AUDIO_FILTERS", "build_nowplaying_embed", "build_queue_embed", "fmt_time",
    "make_ffmpeg_options", "member_is_dj", "progress_bar", "votes_needed", "_youtube_id",
    "FavoritesStore", "YTDLSource", "MusicPlayer",
    "NowPlayingView", "QueueView", "SearchSelectView", "MusicCog", "setup",
]
