"""音源采集器注册表与聚合搜索。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from .core import BaseCrawler, CrawlerError, HttpClient, Track
from .audius import AudiusCrawler
from .itunes import ItunesCrawler

__all__ = [
    "BaseCrawler",
    "CrawlerError",
    "Track",
    "get_crawler",
    "list_sources",
    "search",
]

_http = HttpClient()
CRAWLERS: dict[str, BaseCrawler] = {
    crawler.id: crawler
    for crawler in (AudiusCrawler(_http), ItunesCrawler(_http))
}


def get_crawler(source_id: str) -> BaseCrawler:
    try:
        return CRAWLERS[source_id]
    except KeyError as exc:
        raise CrawlerError(f"未知音源: {source_id}") from exc


def list_sources() -> list[dict[str, str]]:
    return [
        {
            "id": crawler.id,
            "name": crawler.name,
            "description": crawler.description,
            "note": crawler.note,
        }
        for crawler in CRAWLERS.values()
    ]


def search(query: str, source: str = "all", limit: int = 10) -> list[Track]:
    """按关键词搜索；source 为 all 时并发请求全部音源并合并结果。"""
    query = query.strip()
    if not query:
        return []

    if source != "all":
        return get_crawler(source).search(query, limit)

    results: list[Track] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=len(CRAWLERS)) as pool:
        futures = {
            pool.submit(crawler.search, query, limit): crawler
            for crawler in CRAWLERS.values()
        }
        for future, crawler in futures.items():
            try:
                results.extend(future.result())
            except CrawlerError as exc:
                errors.append(f"{crawler.name}: {exc}")

    if not results and errors:
        raise CrawlerError("；".join(errors))
    return results
