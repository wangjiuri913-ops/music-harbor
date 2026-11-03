"""Audius 音源：公开 API，提供独立音乐人的完整曲目。"""

from __future__ import annotations

import os

from .core import BaseCrawler, HttpClient, Track

API_BASE = "https://api.audius.co"
APP_NAME = os.environ.get("AUDIUS_APP_NAME", "MusicHarbor")


class AudiusCrawler(BaseCrawler):
    id = "audius"
    name = "Audius"
    description = "独立音乐平台公开 API，可播放完整曲目"
    note = "完整曲目"

    def __init__(self, http: HttpClient) -> None:
        super().__init__(http)

    def search(self, query: str, limit: int = 20) -> list[Track]:
        cache_key = f"audius:{limit}:{query.lower()}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        payload = self._http.get_json(
            f"{API_BASE}/v1/tracks/search",
            params={"query": query, "app_name": APP_NAME, "limit": limit},
        )
        tracks: list[Track] = []
        for item in payload.get("data") or []:
            track = self._to_track(item)
            if track is not None:
                tracks.append(track)

        self._cache.set(cache_key, tracks)
        return tracks

    def resolve_stream_url(self, track_id: str) -> str:
        # 该地址会 302 到具体的音频节点，requests 会自动跟随。
        return f"{API_BASE}/v1/tracks/{track_id}/stream?app_name={APP_NAME}"

    @staticmethod
    def _to_track(item: dict) -> Track | None:
        if item.get("is_available") is False or item.get("is_delete"):
            return None
        if item.get("is_streamable") is False:
            return None
        access = item.get("access") or {}
        if access.get("stream") is False:
            return None

        user = item.get("user") or {}
        if user.get("is_deactivated"):
            return None

        track_id = str(item.get("id") or "")
        if not track_id:
            return None

        artwork = item.get("artwork") or {}
        permalink = item.get("permalink") or ""

        return Track(
            id=track_id,
            source="audius",
            title=item.get("title") or "未命名曲目",
            artist=user.get("name") or user.get("handle") or "未知音乐人",
            album=item.get("genre") or "",
            duration=int(item.get("duration") or 0),
            cover=artwork.get("480x480") or artwork.get("150x150") or "",
            page_url=f"https://audius.co{permalink}" if permalink else "",
            preview_only=False,
        )
