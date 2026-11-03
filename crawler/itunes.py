"""iTunes 音源：Apple 官方搜索接口，曲库最大，仅提供 30 秒试听片段。"""

from __future__ import annotations

import os

from .core import BaseCrawler, CrawlerError, HttpClient, Track, TTLCache

API_BASE = "https://itunes.apple.com"
# 留空表示使用默认（美国区）商店；部分区域商店对 entity=song 支持不佳，搜索无结果时会自动回退。
COUNTRY = os.environ.get("ITUNES_COUNTRY", "").strip().lower()


class ItunesCrawler(BaseCrawler):
    id = "itunes"
    name = "iTunes"
    description = "Apple 官方搜索接口，主流曲库（30 秒试听）"
    note = "30 秒试听"

    def __init__(self, http: HttpClient) -> None:
        super().__init__(http)
        # track_id -> 试听地址，避免播放时重复请求搜索接口
        self._preview_cache = TTLCache(ttl=21600)

    def search(self, query: str, limit: int = 20) -> list[Track]:
        cache_key = f"itunes:{COUNTRY}:{limit}:{query.lower()}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        payload = self._fetch_search(query, limit, COUNTRY)
        if (payload.get("resultCount") or 0) == 0 and COUNTRY:
            # 某些区域商店搜不到时，回退到默认商店再试一次
            payload = self._fetch_search(query, limit, "")

        tracks: list[Track] = []
        for item in payload.get("results") or []:
            preview = item.get("previewUrl")
            track_id = str(item.get("trackId") or "")
            if not preview or not track_id:
                continue

            track = Track(
                id=track_id,
                source="itunes",
                title=item.get("trackName") or "未命名曲目",
                artist=item.get("artistName") or "未知音乐人",
                album=item.get("collectionName") or "",
                duration=int((item.get("trackTimeMillis") or 0) // 1000),
                cover=self._cover(item.get("artworkUrl100") or ""),
                page_url=item.get("trackViewUrl") or "",
                preview_only=True,
            )
            self._preview_cache.set(track_id, preview)
            tracks.append(track)

        self._cache.set(cache_key, tracks)
        return tracks

    def resolve_stream_url(self, track_id: str) -> str:
        cached = self._preview_cache.get(track_id)
        if cached:
            return cached

        payload = self._http.get_json(f"{API_BASE}/lookup", params={"id": track_id})
        for item in payload.get("results") or []:
            preview = item.get("previewUrl")
            if preview:
                self._preview_cache.set(track_id, preview)
                return preview

        raise CrawlerError("该曲目没有可用的试听地址")

    def _fetch_search(self, query: str, limit: int, country: str) -> dict:
        params = {
            "term": query,
            "media": "music",
            "entity": "song",
            "limit": limit,
            "lang": "zh_cn",
        }
        if country:
            params["country"] = country
        return self._http.get_json(f"{API_BASE}/search", params=params)

    @staticmethod
    def _cover(url: str) -> str:
        return url.replace("100x100bb", "300x300bb") if url else ""
