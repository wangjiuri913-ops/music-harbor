"""MusicHarbor —— 基于公开音乐接口的爬虫 + 网页播放器。"""

from __future__ import annotations

import os
import re
from urllib.parse import quote

import requests
from flask import Flask, Response, jsonify, render_template, request, stream_with_context

from crawler import CrawlerError, get_crawler, list_sources, search

app = Flask(__name__)
app.json.ensure_ascii = False

CONTENT_TYPE_EXT = {
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/x-m4p": "m4a",
    "audio/aac": "aac",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
}

TRACK_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")


@app.get("/")
def index():
    return render_template("index.html", sources=list_sources())


@app.get("/api/sources")
def api_sources():
    return jsonify({"sources": list_sources()})


@app.get("/api/search")
def api_search():
    query = (request.args.get("q") or "").strip()
    source = request.args.get("source") or "all"
    limit = _bounded_int(request.args.get("limit"), default=12, low=1, high=30)

    if not query:
        return jsonify({"error": "请输入搜索关键词"}), 400
    if len(query) > 80:
        return jsonify({"error": "关键词过长，请精简后再搜索"}), 400

    try:
        tracks = search(query, source, limit)
    except CrawlerError as exc:
        return jsonify({"error": str(exc)}), 502

    results = []
    for track in tracks:
        item = track.to_dict()
        stream_path = f"/api/stream/{track.source}/{quote(track.id, safe='')}"
        item["stream_url"] = stream_path
        item["download_url"] = (
            f"{stream_path}?download=1&name="
            f"{quote(f'{track.artist} - {track.title}', safe='')}"
        )
        results.append(item)

    return jsonify({
        "query": query,
        "source": source,
        "count": len(results),
        "results": results,
    })


@app.get("/api/stream/<source>/<track_id>")
def api_stream(source: str, track_id: str):
    """代理音频流：转发 Range 请求以支持拖动进度条，可选触发下载。"""
    if not TRACK_ID_PATTERN.fullmatch(track_id):
        return jsonify({"error": "非法的曲目 ID"}), 400

    try:
        crawler = get_crawler(source)
        upstream = crawler.open_stream(track_id, request.headers.get("Range"))
    except CrawlerError as exc:
        return jsonify({"error": str(exc)}), 502

    content_type = upstream.headers.get("Content-Type") or "audio/mpeg"
    headers = {
        "Content-Type": content_type,
        "Accept-Ranges": upstream.headers.get("Accept-Ranges", "bytes"),
        "Cache-Control": "private, max-age=600",
    }
    for key in ("Content-Length", "Content-Range"):
        value = upstream.headers.get(key)
        if value:
            headers[key] = value

    if request.args.get("download") == "1":
        raw_name = request.args.get("name") or f"{source}-{track_id}"
        base_type = content_type.split(";")[0].strip().lower()
        extension = CONTENT_TYPE_EXT.get(base_type, "mp3")
        filename = f"{_safe_filename(raw_name)}.{extension}"
        headers["Content-Disposition"] = (
            f"attachment; filename*=UTF-8''{quote(filename)}"
        )

    def generate():
        try:
            for chunk in upstream.iter_content(chunk_size=64 * 1024):
                if chunk:
                    yield chunk
        except requests.RequestException:
            pass
        finally:
            upstream.close()

    status = 206 if upstream.status_code == 206 else 200
    return Response(stream_with_context(generate()), status=status, headers=headers)


@app.get("/api/health")
def api_health():
    return jsonify({"status": "ok", "sources": [item["id"] for item in list_sources()]})


@app.errorhandler(404)
def handle_not_found(_error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "接口不存在"}), 404
    return "页面不存在", 404


def _bounded_int(raw: str | None, *, default: int, low: int, high: int) -> int:
    try:
        number = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _safe_filename(raw: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]', " ", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned[:80] or "track"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"MusicHarbor 已启动: http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
