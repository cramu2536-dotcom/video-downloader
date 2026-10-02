# Video Link Downloader

Paste a video link, pick a quality, download the file. Built with Flask and yt-dlp.

## Run locally

1. Install Python 3.9+ and **ffmpeg** (needed to merge HD video and audio, and for MP3 extraction).
   - Windows: `winget install ffmpeg`
   - Mac: `brew install ffmpeg`
   - Ubuntu/Debian: `sudo apt install ffmpeg`
2. In this folder:

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

3. Open http://127.0.0.1:5000

## Put it online (VPS)

```bash
gunicorn -w 2 --timeout 300 -b 0.0.0.0:8000 app:app
```

Put Nginx in front of it and add HTTPS (Let's Encrypt). Set a long proxy timeout in Nginx
(e.g. `proxy_read_timeout 300;`) because downloads are prepared before they start.

## Keep it working

- Sites change often. Update regularly: `pip install -U yt-dlp`
- Limits are at the top of `app.py` (`MAX_DURATION`, `MAX_FILESIZE`, rate limits).
- Files are saved in a temp folder and deleted right after the download finishes.

## Notes

- Without ffmpeg the app still runs, but only single-file formats (often lower quality) are available.
- Add a clear disclaimer (already in the footer) that users must only download content they have rights to.
- Some sites need login or block servers, so those links won't work.
