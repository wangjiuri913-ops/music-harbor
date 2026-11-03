"""爬虫公共基础设施：HTTP 会话、TTL 缓存、曲目模型与基类。"""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass
from typing import Any

import requests

USER_AGENT = "MusicHarbor/1.0 (python crawler for learning)"
DEFAULT_TIMEOUT = 15.0


class CrawlerError(RuntimeError):
    """音源请求失败或返回异常数据时抛出。"""


class TTLCache:
    """线程安全、带过期时间的简易内存缓存，减少对音源的重复请求。"""

    def __init__(self, ttl: float, max_items: int = 512) -> None:
        self._ttl = ttl
        self._max_items = max_items
        self._lock = threading.Lock()
        self._data: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.time() >= expires_at:
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._data) >= self._max_items:
                self._purge_expired_locked()
                if len(self._data) >= self._max_items:
                    self._data.pop(next(iter(self._data)))
            self._data[key] = (time.time() + self._ttl, value)

    def _purge_expired_locked(self) -> None:
        now = time.time()
        for key in [k for k, (expires_at, _) in self._data.items() if expires_at <= now]:
            self._data.pop(key, None)


class HttpClient:
    """为每个线程复用 Session，并为网络错误统一包装成 CrawlerError。"""

    def __init__(self, user_agent: str = USER_AGENT) -> None:
        self._user_agent = user_agent
        self._local = threading.local()

    @property
    def session(self) -> requests.Session:
        session = getattr(self._local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update({"User-Agent": self._user_agent})
            self._local.session = session
        return session

    def get_json(self, url: str, params: dict[str, Any] | None = None,
                 timeout: float = DEFAULT_TIMEOUT) -> Any:
        try:
            response = self.session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise CrawlerError(f"请求音源失败: {exc}") from exc
        except ValueError as exc:
            raise CrawlerError("音源返回的数据不是合法 JSON") from exc

    def get_stream(self, url: str, range_header: str | None = None,
                   timeout: tuple[float, float] = (10, 30)) -> requests.Response:
        headers = {"Accept": "*/*"}
        if range_header:
            headers["Range"] = range_header
        try:
            response = self.session.get(
                url, headers=headers, stream=True, timeout=timeout, allow_redirects=True
            )
        except requests.RequestException as exc:
            raise CrawlerError(f"拉取音频失败: {exc}") from exc
        if response.status_code >= 400:
            response.close()
            raise CrawlerError(f"音源返回状态码 {response.status_code}")
        return response


@dataclass
class Track:
    """统一后的曲目结构，屏蔽不同音源的字段差异。"""

    id: str
    source: str
    title: str
    artist: str
    album: str = ""
    duration: int = 0
    cover: str = ""
    page_url: str = ""
    preview_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["duration_text"] = format_duration(self.duration)
        return data


def format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


class BaseCrawler:
    """音源采集器基类：负责搜索缓存与音频流请求。"""

    id = ""
    name = ""
    description = ""
    note = ""

    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self._cache = TTLCache(ttl=300)

    def search(self, query: str, limit: int = 20) -> list[Track]:
        raise NotImplementedError

    def resolve_stream_url(self, track_id: str) -> str:
        raise NotImplementedError

    def open_stream(self, track_id: str, range_header: str | None = None) -> requests.Response:
        return self._http.get_stream(self.resolve_stream_url(track_id), range_header)
