import ipaddress
import os
import shutil
import socket
import tempfile
from urllib.parse import urlparse

import yt_dlp
from flask import Flask, jsonify, render_template, request, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

MAX_DURATION = 60 * 60            # reject videos longer than 1 hour
MAX_FILESIZE = 1024 * 1024 * 1024  # reject files larger than 1 GB
STANDARD_HEIGHTS = (2160, 1440, 1080, 720, 480, 360, 240)
HAS_FFMPEG = shutil.which("ffmpeg") is not None

app = Flask(__name__)
limiter = Limiter(get_remote_address, app=app, default_limits=["60 per hour"])


def is_safe_url(url: str) -> bool:
    """Allow only public http(s) links (blocks localhost / private network)."""
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            return False
        for info in socket.getaddrinfo(p.hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            if (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_reserved or ip.is_multicast):
                return False
        return True
    except Exception:
        return False


def format_selector(quality: str) -> str:
    if quality == "audio":
        return "bestaudio/best"
    if quality.isdigit():
        h = int(quality)
        if HAS_FFMPEG:
            return f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"
        return f"best[height<={h}]/best"
    return "bestvideo+bestaudio/best" if HAS_FFMPEG else "best"


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/info")
@limiter.limit("20 per minute")
def info():
    url = ((request.get_json(silent=True) or {}).get("url") or "").strip()
    if not is_safe_url(url):
        return jsonify(error="Enter a valid public link that starts with http:// or https://"), 400

    try:
        with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True, "skip_download": True}) as ydl:
            d = ydl.extract_info(url, download=False)
    except Exception:
        return jsonify(error="We couldn't find a downloadable video at this link."), 422

    if d.get("is_live"):
        return jsonify(error="Live streams can't be downloaded."), 422
    if d.get("duration") and d["duration"] > MAX_DURATION:
        return jsonify(error="This video is longer than 1 hour."), 422

    heights = sorted(
        {f["height"] for f in d.get("formats", [])
         if f.get("height") and f.get("vcodec") != "none"},
        reverse=True,
    )
    qualities = [h for h in heights if h in STANDARD_HEIGHTS] or heights[:4]

    return jsonify(
        title=d.get("title") or "Untitled video",
        thumbnail=d.get("thumbnail"),
        duration=d.get("duration"),
        qualities=qualities,
    )


@app.get("/api/download")
@limiter.limit("5 per minute")
def download():
    url = (request.args.get("url") or "").strip()
    quality = (request.args.get("quality") or "best").strip()
    if not is_safe_url(url):
        return jsonify(error="Invalid link."), 400

    tmp = tempfile.mkdtemp(prefix="vd_")
    opts = {
        "format": format_selector(quality),
        "outtmpl": os.path.join(tmp, "%(title).80B.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "restrictfilenames": True,
        "max_filesize": MAX_FILESIZE,
        "match_filter": yt_dlp.utils.match_filter_func(f"!is_live & duration <? {MAX_DURATION}"),
    }
    if HAS_FFMPEG:
        if quality == "audio":
            opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]
        else:
            opts["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        files = [os.path.join(tmp, f) for f in os.listdir(tmp)]
        if not files:
            raise RuntimeError("no file produced")
        path = max(files, key=os.path.getsize)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        return jsonify(error="Download failed. The file may be too large or not available."), 500

    resp = send_file(path, as_attachment=True)
    resp.call_on_close(lambda: shutil.rmtree(tmp, ignore_errors=True))
    return resp


if __name__ == "__main__":
    app.run(debug=True)
