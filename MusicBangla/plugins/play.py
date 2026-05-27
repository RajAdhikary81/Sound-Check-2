import os
import asyncio
import time
import re
import random
import yt_dlp
import httpx
from collections import deque
from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from pytgcalls.types import MediaStream
from pytgcalls import filters as ptg_filters

import config
from MusicBangla import app, assistant, calls, LOGGER


os.makedirs("downloads", exist_ok=True)

# =====================================================
# QUEUE SYSTEM
# =====================================================

ACTIVE_CHATS = {}   # chat_id -> current song info
QUEUES = {}         # chat_id -> deque of (query, video, requester_mention)

_USER_COOLDOWN = {}
_COOLDOWN_SECONDS = 5
_GLOBAL_SPAM = {}
_MAX_CONCURRENT = 3

# --- Cookies ---
_COOKIE_FILE = None

def _fix_cookie_line(line: str) -> str:
    line = line.strip()
    if not line or line.startswith("#"):
        return line
    parts = line.split()
    if len(parts) >= 7:
        return "\t".join(parts[:6]) + "\t" + " ".join(parts[6:])
    elif len(parts) == 6:
        return "\t".join(parts) + "\t"
    return line


def load_cookies_from_env() -> bool:
    """Load/reload cookies from YT_COOKIES env var. Returns True if loaded."""
    global _COOKIE_FILE
    raw_cookies = os.environ.get("YT_COOKIES", "")
    if not raw_cookies:
        if os.path.exists("cookies.txt"):
            _COOKIE_FILE = "cookies.txt"
            return True
        return False

    try:
        raw = raw_cookies.replace("\\n", "\n")
        lines = raw.split("\n")
        fixed = ["# Netscape HTTP Cookie File"]
        for line in lines:
            line = line.strip()
            if not line or "Netscape" in line or "HTTP Cookie" in line:
                continue
            if line.startswith("#"):
                fixed.append(line)
                continue
            fixed.append(_fix_cookie_line(line))
        with open("cookies.txt", "w") as f:
            f.write("\n".join(fixed) + "\n")
        _COOKIE_FILE = "cookies.txt"
        cookie_count = sum(1 for l in fixed if l and not l.startswith("#"))
        LOGGER.info(f"YouTube cookies loaded: {cookie_count} cookies")
        return True
    except Exception as e:
        LOGGER.error(f"Cookie write error: {e}")
        return False


# Load cookies on startup
load_cookies_from_env()


# =====================================================
# COLORFUL BUTTON THEMES (rotating colors)
# =====================================================

_BUTTON_THEMES = [
    {"song": "🔗", "add": "➕", "channel": "📢", "support": "💬", "owner": "👨‍💻", "close": "❌"},
    {"song": "🎵", "add": "🌟", "channel": "🔔", "support": "💖", "owner": "🧑‍🎤", "close": "🚫"},
    {"song": "🎧", "add": "✨", "channel": "📣", "support": "💜", "owner": "🎤", "close": "🔴"},
    {"song": "🎶", "add": "🌈", "channel": "📡", "support": "💙", "owner": "🎸", "close": "⛔"},
    {"song": "💿", "add": "🔥", "channel": "🎺", "support": "💚", "owner": "🎹", "close": "🛑"},
    {"song": "🎼", "add": "⭐", "channel": "📻", "support": "🧡", "owner": "🎻", "close": "❎"},
    {"song": "🎙️", "add": "💫", "channel": "🎷", "support": "💛", "owner": "🎯", "close": "🔻"},
]

def _get_theme():
    return random.choice(_BUTTON_THEMES)


# =====================================================
# YT-DLP BASE OPTIONS
# =====================================================

def _base_opts():
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 5,
        "fragment_retries": 5,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "no_check_formats": True,
        "check_formats": False,
        "source_address": "0.0.0.0",
        "extractor_retries": 3,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }
    return opts


def cleanup_downloads():
    try:
        for f in os.listdir("downloads"):
            fpath = os.path.join("downloads", f)
            if os.path.isfile(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass
    except Exception:
        pass


# =====================================================
# INLINE BUTTONS for now-playing message (COLORFUL)
# =====================================================

def _play_buttons(song_link: str = "") -> InlineKeyboardMarkup:
    t = _get_theme()
    rows = []
    row1 = []
    if song_link and song_link.startswith("http"):
        row1.append(InlineKeyboardButton(f"{t['song']} গান দেখো", url=song_link))
    row1.append(
        InlineKeyboardButton(
            f"{t['add']} গ্রুপে যোগ করো",
            url="https://t.me/MusicBanglaBot?startgroup=true",
        )
    )
    rows.append(row1)
    rows.append([
        InlineKeyboardButton(f"{t['channel']} চ্যানেল", url=config.SUPPORT_CHANNEL),
        InlineKeyboardButton(f"{t['support']} সাপোর্ট", url=config.SUPPORT_GROUP),
    ])
    rows.append([
        InlineKeyboardButton(
            f"{t['owner']} মালিক",
            url=f"https://t.me/{config.OWNER_USERNAME}",
        ),
        InlineKeyboardButton(f"{t['close']} বন্ধ করো", callback_data="close_play_msg"),
    ])
    return InlineKeyboardMarkup(rows)


# =====================================================
# FIND DOWNLOADED FILE HELPER
# =====================================================

def _find_downloaded_file(prefix, track_id, ydl=None, info=None):
    for ext in [".m4a", ".mp3", ".webm", ".opus", ".ogg", ".wav", ".mp4", ".mkv", ".3gp"]:
        candidate = f"downloads/{prefix}{track_id}{ext}"
        if os.path.exists(candidate):
            return candidate

    if ydl and info:
        try:
            fname = ydl.prepare_filename(info)
            base = os.path.splitext(fname)[0]
            for ext in [".m4a", ".mp3", ".webm", ".opus", ".ogg", ".mp4", ".mkv"]:
                if os.path.exists(base + ext):
                    return base + ext
            if os.path.exists(fname):
                return fname
        except Exception:
            pass

    try:
        files = [f for f in os.listdir("downloads") if f.startswith(prefix)]
        if files:
            files.sort(
                key=lambda x: os.path.getmtime(os.path.join("downloads", x)),
                reverse=True,
            )
            return os.path.join("downloads", files[0])
    except Exception:
        pass

    return None


# =====================================================
# SOURCE 1: SOUNDCLOUD (via yt-dlp — most reliable)
# =====================================================

def _soundcloud_search_and_download(query: str, video: bool):
    """Search SoundCloud and download. No external APIs needed."""
    LOGGER.info(f"SoundCloud search: {query}")
    cleanup_downloads()

    try:
        opts = _base_opts()
        opts["outtmpl"] = "downloads/sc_%(id)s.%(ext)s"
        opts["format"] = "best"

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"scsearch5:{query}", download=False)

            entries = []
            if info and info.get("_type") == "playlist" and info.get("entries"):
                entries = list(info["entries"])

            if not entries:
                LOGGER.warning("SoundCloud: no search results")
                return None, None

            # Pick best match
            best = _pick_best_match(entries, query) or entries[0]
            webpage_url = best.get("webpage_url") or best.get("url")
            if not webpage_url:
                return None, None

        # Download in a separate instance
        LOGGER.info(f"SoundCloud: downloading '{best.get('title', '?')}'")
        dl_opts = _base_opts()
        dl_opts["outtmpl"] = "downloads/sc_%(id)s.%(ext)s"
        dl_opts["format"] = "best"

        with yt_dlp.YoutubeDL(dl_opts) as ydl2:
            dl_info = ydl2.extract_info(webpage_url, download=True)

            title = dl_info.get("title", best.get("title", "Unknown"))
            duration = dl_info.get("duration", best.get("duration", 0))
            uploader = dl_info.get("uploader", best.get("uploader", "SoundCloud"))
            thumb = dl_info.get("thumbnail", best.get("thumbnail", ""))
            webpage = dl_info.get("webpage_url", webpage_url)
            track_id = dl_info.get("id", best.get("id", "unknown"))

            local_path = _find_downloaded_file("sc_", track_id, ydl2, dl_info)

            if local_path and os.path.getsize(local_path) > 5000:
                LOGGER.info(f"SoundCloud OK: {title} -> {local_path}")
                return local_path, {
                    "title": title,
                    "duration": int(duration) if duration else 0,
                    "channel": uploader,
                    "thumb": thumb,
                    "link": webpage,
                    "source": "SoundCloud",
                }

        return None, None

    except Exception as e:
        LOGGER.error(f"SoundCloud error: {e}")
        return None, None


# =====================================================
# SOURCE 2: JIOSAAVN API (free, no auth — Hindi/Bengali)
# =====================================================

_JIOSAAVN_API_BASES = [
    "https://saavn.dev/api",
    "https://jiosaavn-api-privatecvc2.vercel.app/api",
]

def _jiosaavn_search_and_download(query: str, video: bool):
    """Search JioSaavn and download via free public API."""
    LOGGER.info(f"JioSaavn search: {query}")
    cleanup_downloads()

    for api_base in _JIOSAAVN_API_BASES:
        try:
            with httpx.Client(timeout=20, follow_redirects=True) as client:
                # Search
                resp = client.get(
                    f"{api_base}/search/songs",
                    params={"query": query, "limit": 5},
                )
                if resp.status_code != 200:
                    LOGGER.warning(f"JioSaavn [{api_base}]: search status {resp.status_code}")
                    continue

                data = resp.json()
                results = data.get("data", {}).get("results", [])
                if not results:
                    results = data.get("results", [])
                if not results:
                    LOGGER.warning(f"JioSaavn [{api_base}]: no results")
                    continue

                # Pick best match
                song = results[0]
                for r in results:
                    r_title = (r.get("name") or r.get("title") or "").lower()
                    if query.lower() in r_title or r_title in query.lower():
                        song = r
                        break

                song_id = song.get("id", "")
                title = song.get("name") or song.get("title") or "Unknown"
                duration = song.get("duration", 0)
                artists = song.get("artists", {})
                if isinstance(artists, dict):
                    primary = artists.get("primary", [])
                    artist_name = ", ".join(a.get("name", "") for a in primary[:2]) if primary else "Unknown"
                elif isinstance(artists, str):
                    artist_name = artists
                else:
                    artist_name = song.get("primaryArtists", song.get("artist", "Unknown"))
                thumb = ""
                images = song.get("image", [])
                if isinstance(images, list) and images:
                    thumb = images[-1].get("url", images[-1].get("link", ""))
                elif isinstance(images, str):
                    thumb = images
                song_url = song.get("url", song.get("perma_url", ""))

                # Get download URLs
                dl_urls = song.get("downloadUrl", [])
                if not dl_urls:
                    # Try fetching song details by ID
                    detail_resp = client.get(
                        f"{api_base}/songs/{song_id}",
                    )
                    if detail_resp.status_code == 200:
                        detail_data = detail_resp.json()
                        song_detail = detail_data.get("data", [detail_data])
                        if isinstance(song_detail, list) and song_detail:
                            song_detail = song_detail[0]
                        dl_urls = song_detail.get("downloadUrl", [])
                        if not dl_urls:
                            continue
                    else:
                        continue

                # Pick highest quality download URL
                if isinstance(dl_urls, list):
                    # Sort by quality (320kbps > 160kbps > 96kbps)
                    dl_urls.sort(
                        key=lambda x: int(x.get("quality", "0").replace("kbps", "").strip() or 0),
                        reverse=True,
                    )
                    audio_url = dl_urls[0].get("url", dl_urls[0].get("link", ""))
                elif isinstance(dl_urls, str):
                    audio_url = dl_urls
                else:
                    continue

                if not audio_url:
                    continue

                # Download audio file
                dl_resp = client.get(audio_url, follow_redirects=True)
                if dl_resp.status_code != 200 or len(dl_resp.content) < 5000:
                    LOGGER.warning(f"JioSaavn [{api_base}]: download failed, size={len(dl_resp.content)}")
                    continue

                ext = ".m4a"
                ct = dl_resp.headers.get("content-type", "")
                if "mp4" in ct or "m4a" in ct:
                    ext = ".m4a"
                elif "mp3" in ct or "mpeg" in ct:
                    ext = ".mp3"

                local_path = f"downloads/js_{song_id}{ext}"
                with open(local_path, "wb") as f:
                    f.write(dl_resp.content)

                if os.path.exists(local_path) and os.path.getsize(local_path) > 5000:
                    LOGGER.info(f"JioSaavn OK [{api_base}]: {title} -> {local_path}")
                    return local_path, {
                        "title": title,
                        "duration": int(duration) if duration else 0,
                        "channel": artist_name,
                        "thumb": thumb,
                        "link": song_url,
                        "source": "JioSaavn",
                    }

        except Exception as e:
            LOGGER.warning(f"JioSaavn [{api_base}]: {str(e)[:80]}")
            continue

    return None, None


# =====================================================
# SOURCE 3: YOUTUBE (via yt-dlp — multiple clients)
# =====================================================

def _youtube_search(query: str):
    """Search YouTube via yt-dlp flat search."""
    # Try multiple search strategies
    search_strategies = []
    if _COOKIE_FILE:
        search_strategies.append((_COOKIE_FILE, ["web_creator"], "cookies+web_creator"))
    search_strategies.append((None, ["mediaconnect"], "mediaconnect"))
    search_strategies.append((None, ["web_creator"], "web_creator"))
    search_strategies.append((None, None, "default"))

    for cookie, player_client, desc in search_strategies:
        try:
            opts = _base_opts()
            opts["extract_flat"] = True
            if cookie:
                opts["cookiefile"] = cookie
            if player_client:
                opts["extractor_args"] = {"youtube": {"player_client": player_client}}

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch3:{query}", download=False)

                entries = []
                if info and info.get("_type") == "playlist" and info.get("entries"):
                    entries = list(info["entries"])

                if not entries:
                    continue

                best = _pick_best_match(entries, query) or entries[0]
                vid = best.get("id") or best.get("url", "")
                LOGGER.info(f"YT search OK [{desc}]: {best.get('title', '?')}")
                return {
                    "title": best.get("title", "Unknown"),
                    "duration": int(best.get("duration", 0) or 0),
                    "link": f"https://www.youtube.com/watch?v={vid}",
                    "thumb": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                    "channel": best.get("channel", "") or best.get("uploader", "YouTube"),
                    "id": vid,
                    "source": "YouTube",
                }
        except Exception as e:
            LOGGER.warning(f"YT search [{desc}]: {str(e)[:80]}")
            continue

    return None


def _youtube_download(url: str, video: bool) -> str:
    """Download from YouTube using multiple client strategies including
    mediaconnect (no cookies needed, bypasses bot detection)."""
    cleanup_downloads()
    suffix = "_v" if video else ""
    outtmpl = f"downloads/yt_%(id)s{suffix}.%(ext)s"

    if video:
        fmt = (
            "best[height<=480][ext=mp4]/best[height<=480][ext=webm]/"
            "best[height<=480]/best[ext=mp4]/best"
        )
    else:
        fmt = (
            "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio[ext=opus]/"
            "bestaudio[ext=webm]/bestaudio/best[height<=360]/best"
        )

    # mediaconnect client bypasses bot detection without cookies
    strategies = []
    strategies.append((None, ["mediaconnect"], "mediaconnect"))
    if _COOKIE_FILE:
        strategies.append((_COOKIE_FILE, ["web_creator"], "cookies+web_creator"))
        strategies.append((_COOKIE_FILE, ["ios"], "cookies+ios"))
        strategies.append((_COOKIE_FILE, ["web"], "cookies+web"))
    strategies.append((None, ["web_creator"], "web_creator"))
    strategies.append((None, ["ios"], "ios"))
    strategies.append((None, ["tv"], "tv"))
    strategies.append((None, ["mweb"], "mweb"))
    strategies.append((None, None, "default"))

    for cookie, player_client, desc in strategies:
        opts = _base_opts()
        opts["format"] = fmt
        opts["outtmpl"] = outtmpl
        if cookie:
            opts["cookiefile"] = cookie
        if player_client:
            opts["extractor_args"] = {"youtube": {"player_client": player_client}}
        opts["postprocessors"] = []

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                fname = ydl.prepare_filename(info)
                base = os.path.splitext(fname)[0]
                for ext in [".m4a", ".mp3", ".webm", ".opus", ".ogg", ".mp4", ".mkv", ".3gp"]:
                    if os.path.exists(base + ext):
                        fpath = base + ext
                        if os.path.getsize(fpath) > 5000:
                            LOGGER.info(f"YT OK [{desc}]: {fpath}")
                            return fpath
                if os.path.exists(fname) and os.path.getsize(fname) > 5000:
                    LOGGER.info(f"YT OK [{desc}]: {fname}")
                    return fname
        except Exception as e:
            emsg = str(e)[:120]
            LOGGER.warning(f"YT [{desc}]: {emsg}")
            # If bot detection, skip cookie-less strategies that will also fail
            if "Sign in to confirm" in emsg and not cookie:
                continue
        time.sleep(0.3)

    return None


# =====================================================
# SOURCE 4: INVIDIOUS API (YouTube alternative frontend)
# =====================================================

_INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net",
    "https://invidious.nerdvpn.de",
    "https://iv.datura.network",
    "https://invidious.private.coffee",
    "https://yt.artemislena.eu",
]

def _invidious_search_and_download(query: str, video: bool):
    """Search and download via Invidious API (YouTube frontend)."""
    LOGGER.info(f"Invidious search: {query}")
    cleanup_downloads()

    for api_base in _INVIDIOUS_INSTANCES:
        try:
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                resp = client.get(
                    f"{api_base}/api/v1/search",
                    params={"q": query, "type": "video", "sort_by": "relevance"},
                    headers={"Accept": "application/json"},
                )
                if resp.status_code != 200:
                    continue

                results = resp.json()
                if not results or not isinstance(results, list):
                    continue

                # Find first video result
                best = None
                for item in results[:5]:
                    if item.get("type") == "video":
                        best = item
                        break
                if not best:
                    continue

                vid_id = best.get("videoId", "")
                if not vid_id:
                    continue

                # Get video details with audio streams
                vid_resp = client.get(
                    f"{api_base}/api/v1/videos/{vid_id}",
                    headers={"Accept": "application/json"},
                )
                if vid_resp.status_code != 200:
                    continue

                vid_data = vid_resp.json()
                adaptive = vid_data.get("adaptiveFormats", [])

                # Filter audio-only streams
                audio_streams = [
                    s for s in adaptive
                    if s.get("type", "").startswith("audio/")
                ]
                if not audio_streams:
                    continue

                # Sort by bitrate (highest first)
                audio_streams.sort(key=lambda x: int(x.get("bitrate", 0) or 0), reverse=True)
                stream_url = audio_streams[0].get("url", "")
                if not stream_url:
                    continue

                # Download
                title = vid_data.get("title", best.get("title", "Unknown"))
                duration = vid_data.get("lengthSeconds", best.get("lengthSeconds", 0))

                dl_resp = client.get(stream_url, follow_redirects=True, timeout=30)
                if dl_resp.status_code != 200 or len(dl_resp.content) < 5000:
                    continue

                mime = audio_streams[0].get("type", "")
                if "mp4" in mime or "m4a" in mime:
                    ext = ".m4a"
                elif "webm" in mime or "opus" in mime:
                    ext = ".webm"
                else:
                    ext = ".m4a"

                local_path = f"downloads/inv_{vid_id}{ext}"
                with open(local_path, "wb") as f:
                    f.write(dl_resp.content)

                if os.path.exists(local_path) and os.path.getsize(local_path) > 5000:
                    LOGGER.info(f"Invidious OK [{api_base}]: {title}")
                    return local_path, {
                        "title": title,
                        "duration": int(duration) if duration else 0,
                        "channel": vid_data.get("author", best.get("author", "YouTube")),
                        "thumb": f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg",
                        "link": f"https://www.youtube.com/watch?v={vid_id}",
                        "source": "YouTube (Invidious)",
                    }

        except Exception as e:
            LOGGER.warning(f"Invidious [{api_base}]: {str(e)[:80]}")
            continue

    return None, None


# =====================================================
# SOURCE 5: DIRECT YT-DLP for any URL (generic)
# =====================================================

def _generic_ytdlp_download(url: str, video: bool):
    """Download from any yt-dlp supported URL (SoundCloud direct, Deezer, etc)."""
    LOGGER.info(f"Generic yt-dlp download: {url}")
    cleanup_downloads()

    if video:
        fmt = "best[height<=480]/best"
    else:
        fmt = "bestaudio[ext=m4a]/bestaudio/best"

    opts = _base_opts()
    opts["format"] = fmt
    opts["outtmpl"] = "downloads/gen_%(id)s.%(ext)s"
    if _COOKIE_FILE:
        opts["cookiefile"] = _COOKIE_FILE

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None, None

            track_id = info.get("id", "unknown")
            local_path = _find_downloaded_file("gen_", track_id, ydl, info)

            if local_path and os.path.getsize(local_path) > 5000:
                title = info.get("title", "Unknown")
                LOGGER.info(f"Generic OK: {title}")
                return local_path, {
                    "title": title,
                    "duration": int(info.get("duration", 0) or 0),
                    "channel": info.get("uploader", info.get("artist", "Unknown")),
                    "thumb": info.get("thumbnail", ""),
                    "link": info.get("webpage_url", url),
                    "source": info.get("extractor", "Direct"),
                }
    except Exception as e:
        LOGGER.warning(f"Generic yt-dlp error: {str(e)[:100]}")

    return None, None


# =====================================================
# URL HANDLING: Spotify, Apple Music, etc.
# =====================================================

def _extract_song_from_url(url: str) -> str:
    """Extract song name from streaming service URL."""
    # Try yt-dlp first
    try:
        opts = _base_opts()
        opts["extract_flat"] = True
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title") or info.get("track") or ""
            artist = info.get("artist") or info.get("uploader") or ""
            if title:
                return f"{artist} {title}".strip() if artist else title
    except Exception as e:
        LOGGER.warning(f"URL extract (yt-dlp): {str(e)[:60]}")

    # Fallback: scrape the page title
    try:
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                import html
                match = re.search(r'<title[^>]*>([^<]+)</title>', resp.text, re.IGNORECASE)
                if match:
                    raw = html.unescape(match.group(1))
                    for suf in [" - Spotify", " on Apple Music", " | Spotify",
                                " - song and lyrics", " - JioSaavn", " - Gaana",
                                " | JioSaavn", " | Gaana", " - Amazon Music",
                                " - Resso", " | Amazon Music", " | Resso",
                                " - YouTube Music", " | YouTube Music",
                                " - Wynk Music", " | Wynk", " - YouTube",
                                " | YouTube", " - Deezer", " | Deezer",
                                " - Tidal", " | Tidal", " - Listen on",
                                " | Listen on"]:
                        raw = raw.replace(suf, "")
                    return raw.strip()
    except Exception:
        pass

    return ""


def _is_streaming_url(url: str) -> str:
    patterns = {
        "Spotify": r'https?://(open\.)?spotify\.com/',
        "Apple Music": r'https?://music\.apple\.com/',
        "JioSaavn": r'https?://(www\.)?jiosaavn\.com/',
        "Gaana": r'https?://(www\.)?gaana\.com/',
        "Wynk": r'https?://(www\.)?wynk\.in/',
        "Deezer": r'https?://(www\.)?deezer\.com/',
        "Tidal": r'https?://(www\.)?tidal\.com/',
        "SoundCloud": r'https?://(www\.|m\.)?soundcloud\.com/',
        "Amazon Music": r'https?://music\.amazon\.',
        "YouTube Music": r'https?://music\.youtube\.com/',
        "Resso": r'https?://(www\.)?resso\.com/',
    }
    for name, pattern in patterns.items():
        if re.match(pattern, url, re.IGNORECASE):
            return name
    return ""


# =====================================================
# MASTER SEARCH: multi-source with robust fallback
# =====================================================

def search_and_get_media(query: str, video: bool):
    """
    Multi-source search (no external API keys needed):
      1. JioSaavn (free API — best for Hindi/Bengali/Indian songs)
      2. YouTube (yt-dlp with cookies + multiple client strategies)
      3. Invidious (YouTube alternative frontend, no cookies)
      4. SoundCloud (fallback — global music catalog)
      5. Query variations as last resort
    """
    errors = []

    # === Source 1: JioSaavn ===
    LOGGER.info("=== Source 1: JioSaavn ===")
    try:
        path, info = _jiosaavn_search_and_download(query, video)
        if path and info:
            return path, info
        errors.append("JioSaavn: no results")
    except Exception as e:
        errors.append(f"JS: {str(e)[:50]}")

    # === Source 2: YouTube (yt-dlp) ===
    LOGGER.info("=== Source 2: YouTube ===")
    try:
        yt_info = _youtube_search(query)
        if yt_info:
            path = _youtube_download(yt_info["link"], video)
            if path:
                return path, yt_info
            errors.append("YouTube: download failed (bot detection)")
        else:
            errors.append("YouTube: search failed")
    except Exception as e:
        errors.append(f"YT: {str(e)[:50]}")

    # === Source 3: Invidious (YouTube alt frontend) ===
    LOGGER.info("=== Source 3: Invidious ===")
    try:
        path, info = _invidious_search_and_download(query, video)
        if path and info:
            return path, info
        errors.append("Invidious: no results")
    except Exception as e:
        errors.append(f"Inv: {str(e)[:50]}")

    # === Source 4: SoundCloud ===
    LOGGER.info("=== Source 4: SoundCloud ===")
    try:
        path, info = _soundcloud_search_and_download(query, video)
        if path and info:
            return path, info
        errors.append("SoundCloud: no results")
    except Exception as e:
        errors.append(f"SC: {str(e)[:50]}")

    # === Source 5: Query variations on JioSaavn + SoundCloud ===
    LOGGER.info("=== Source 5: Query variations ===")
    variations = []
    q_lower = query.lower()
    if "official" not in q_lower:
        variations.append(f"{query} official audio")
    variations.append(f"{query} audio")

    for alt_query in variations[:2]:
        try:
            path, info = _jiosaavn_search_and_download(alt_query, video)
            if path and info:
                return path, info
        except Exception:
            pass
        try:
            path, info = _soundcloud_search_and_download(alt_query, video)
            if path and info:
                return path, info
        except Exception:
            pass

    raise Exception(f"All sources failed: {'; '.join(errors)}")


# =====================================================
# SMART MATCHING
# =====================================================

def _pick_best_match(entries, query):
    query_lower = query.lower().strip()
    query_words = set(query_lower.split())
    wants_remix = any(w in query_lower for w in ["remix", "slowed", "reverb", "lofi", "lo-fi"])

    best_entry = None
    best_score = -999

    for entry in entries:
        title = (entry.get("title") or "").lower()
        if not title:
            continue

        title_words = set(title.split())
        overlap = len(query_words & title_words)
        substring_bonus = 3 if query_lower in title else 0
        substring_bonus += 2 if title in query_lower else 0

        bad_words = ["slowed", "reverb", "reverbed", "lofi", "lo-fi", "8d", "bass boosted", "nightcore"]
        penalty = 0
        if not wants_remix:
            for bw in bad_words:
                if bw in title and bw not in query_lower:
                    penalty += 5

        len_penalty = abs(len(title) - len(query_lower)) / max(len(query_lower), 1) * 0.3
        official_bonus = 1 if any(w in title for w in ["original", "official"]) else 0
        dur = entry.get("duration", 0) or 0
        short_penalty = 3 if dur and dur < 60 else 0

        score = overlap + substring_bonus + official_bonus - penalty - len_penalty - short_penalty
        if score > best_score:
            best_score = score
            best_entry = entry

    return best_entry


# =====================================================
# HELPERS
# =====================================================

def fmt_dur(s):
    if not s:
        return "Live"
    try:
        s = int(s)
        return f"{s // 60}:{s % 60:02d}"
    except Exception:
        return str(s)


async def safe_react(client, message, emoji):
    try:
        await client.send_reaction(
            chat_id=message.chat.id, message_id=message.id, emoji=emoji)
    except Exception:
        pass


async def ensure_assistant(chat_id: int):
    try:
        me = await assistant.get_me()
        await assistant.get_chat_member(chat_id, me.id)
        return True
    except Exception:
        pass

    try:
        invite = await app.export_chat_invite_link(chat_id)
        await assistant.join_chat(invite)
        await asyncio.sleep(5)
        return True
    except Exception:
        pass

    try:
        chat = await app.get_chat(chat_id)
        if chat.username:
            await assistant.join_chat(chat.username)
            await asyncio.sleep(5)
            return True
    except Exception:
        pass

    LOGGER.error(f"Could not join {chat_id}")
    return False


async def try_play_stream(chat_id, media_path, video, max_retries=4):
    if video:
        stream = MediaStream(
            media_path,
            video_flags=MediaStream.Flags.AUTO_DETECT,
        )
    else:
        stream = MediaStream(
            media_path,
            video_flags=MediaStream.Flags.IGNORE,
        )

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            await calls.play(chat_id, stream)
            LOGGER.info(f"Playing in {chat_id} (attempt {attempt})")
            return True
        except Exception as e:
            last_error = e
            err = str(e).lower()
            if "no active group call" in err or "group_call_invalid" in err:
                if attempt < max_retries:
                    await asyncio.sleep(3)
                    continue
                return "NO_VC"
            elif "chat_admin_required" in err or "not found" in err:
                return "NO_PERM"
            elif "file_part" in err or "file_reference" in err:
                # File issue — retry with fresh stream
                if video:
                    stream = MediaStream(
                        media_path,
                        video_flags=MediaStream.Flags.AUTO_DETECT,
                    )
                else:
                    stream = MediaStream(
                        media_path,
                        video_flags=MediaStream.Flags.IGNORE,
                    )
                if attempt < max_retries:
                    await asyncio.sleep(2)
                    continue
                return f"ERROR: {str(e)[:100]}"
            else:
                if attempt < max_retries:
                    await asyncio.sleep(3)
                    continue
                return f"ERROR: {str(e)[:100]}"

    return f"FAILED: {str(last_error)[:100]}"


# =====================================================
# NOW-PLAYING message
# =====================================================

_NP_THEMES = [
    {"bar": "🟣", "icon": "🎵", "vid": "🎬"},
    {"bar": "🔵", "icon": "🎶", "vid": "📹"},
    {"bar": "🟢", "icon": "🎧", "vid": "🎥"},
    {"bar": "🟡", "icon": "🎼", "vid": "📽️"},
    {"bar": "🔴", "icon": "🎙️", "vid": "🎞️"},
    {"bar": "🟠", "icon": "💿", "vid": "📺"},
]

def _build_now_playing(info: dict, video: bool, requester: str,
                       queue_len: int = 0) -> str:
    t = random.choice(_NP_THEMES)
    icon = t["vid"] if video else t["icon"]
    mode = "ভিডিও" if video else "অডিও"
    source_name = info.get("source", "?")
    bar = t["bar"]

    caption = (
        f"╭{'─' * 23}╮\n"
        f"  {icon} <b>এখন {mode} বাজছে</b>\n"
        f"╰{'─' * 23}╯\n\n"
        f"{bar} <b>শিরোনাম:</b> {info.get('title', '?')}\n"
        f"⏱ <b>সময়:</b> <code>{fmt_dur(info.get('duration'))}</code>\n"
        f"🎤 <b>শিল্পী:</b> {info.get('channel', '?')}\n"
        f"📡 <b>সোর্স:</b> {source_name}\n"
        f"🎧 <b>মোড:</b> {mode}\n"
        f"🙋 <b>অনুরোধ:</b> {requester}\n"
    )
    if queue_len > 0:
        caption += f"📋 <b>কিউতে বাকি:</b> {queue_len} টি\n"
    caption += (
        f"\n╭── <b>কন্ট্রোল</b> ──╮\n"
        f"⏸ <code>/pause</code>  ▶️ <code>/resume</code>\n"
        f"⏭ <code>/skip</code>   🛑 <code>/stop</code>\n"
        f"📋 <code>/queue</code>\n"
        f"╰─────────────────╯"
    )
    return caption


async def send_now_playing(chat_id, info, video, requester, queue_len=0):
    caption = _build_now_playing(info, video, requester, queue_len)
    buttons = _play_buttons(info.get("link", ""))
    thumb = info.get("thumb", "")
    try:
        if thumb and thumb.startswith("http"):
            await app.send_photo(
                chat_id, photo=thumb, caption=caption, reply_markup=buttons
            )
        else:
            await app.send_message(chat_id, caption, reply_markup=buttons)
    except Exception:
        try:
            await app.send_message(chat_id, caption, reply_markup=buttons)
        except Exception:
            await app.send_message(chat_id, caption)


# =====================================================
# QUEUE: auto-play next song
# =====================================================

async def play_next_in_queue(chat_id: int):
    LOGGER.info(f"play_next_in_queue for {chat_id}")
    ACTIVE_CHATS.pop(chat_id, None)

    if chat_id not in QUEUES or not QUEUES[chat_id]:
        LOGGER.info(f"Queue empty for {chat_id}, leaving VC")
        try:
            await calls.leave_call(chat_id)
        except Exception:
            pass
        try:
            await app.send_message(
                chat_id,
                "🎵 <b>কিউ শেষ!</b>\nআরো গান শুনতে <code>/play</code> দাও।",
            )
        except Exception:
            pass
        return

    next_query, next_video, requester = QUEUES[chat_id].popleft()
    LOGGER.info(f"Auto-playing next: '{next_query}' for {chat_id}")

    try:
        status = await app.send_message(
            chat_id,
            f"⏭ <b>পরবর্তী গান লোড হচ্ছে...</b>\n🔎 {next_query}",
        )
    except Exception:
        status = None

    try:
        loop = asyncio.get_event_loop()

        # Handle URLs in queued items
        search_query = next_query
        if next_query.startswith("http"):
            streaming_service = _is_streaming_url(next_query)
            if streaming_service or re.match(
                r'https?://(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/', next_query
            ):
                if streaming_service:
                    extracted = await loop.run_in_executor(
                        None, _extract_song_from_url, next_query
                    )
                    if extracted:
                        search_query = extracted

                # Try direct download for YouTube URLs
                if re.match(r'https?://(www\.)?(youtube\.com|youtu\.be)/', next_query):
                    yt_path = await loop.run_in_executor(
                        None, _youtube_download, next_query, next_video
                    )
                    if yt_path:
                        yt_info = {
                            "title": "YouTube", "duration": 0, "channel": "YouTube",
                            "thumb": "", "link": next_query, "source": "YouTube",
                        }
                        result = await try_play_stream(chat_id, str(yt_path), next_video)
                        if result is True:
                            ACTIVE_CHATS[chat_id] = yt_info
                            if status:
                                try:
                                    await status.delete()
                                except Exception:
                                    pass
                            queue_len = len(QUEUES.get(chat_id, []))
                            await send_now_playing(chat_id, yt_info, next_video, requester, queue_len)
                            return

        media_path, info = await loop.run_in_executor(
            None, search_and_get_media, search_query, next_video
        )

        if not media_path:
            if status:
                await status.edit("❌ পরবর্তী গান পাওয়া যায়নি।")
            await asyncio.sleep(2)
            await play_next_in_queue(chat_id)
            return

        result = await try_play_stream(chat_id, str(media_path), next_video)

        if result is True:
            ACTIVE_CHATS[chat_id] = info
            if status:
                try:
                    await status.delete()
                except Exception:
                    pass
            queue_len = len(QUEUES.get(chat_id, []))
            await send_now_playing(chat_id, info, next_video, requester, queue_len)
        else:
            if status:
                await status.edit(f"❌ পরবর্তী গান চালানো যায়নি: {result}")
            await asyncio.sleep(2)
            await play_next_in_queue(chat_id)

    except Exception as e:
        LOGGER.error(f"Auto-play error: {e}")
        if status:
            try:
                await status.edit(f"❌ ত্রুটি: <code>{str(e)[:80]}</code>")
            except Exception:
                pass
        await asyncio.sleep(2)
        await play_next_in_queue(chat_id)


@calls.on_update(ptg_filters.stream_end)
async def _on_stream_end(client, update):
    chat_id = update.chat_id
    LOGGER.info(f"Stream ended in {chat_id}")
    await play_next_in_queue(chat_id)


# =====================================================
# SECURITY
# =====================================================

def _sanitize_query(text: str) -> str:
    text = text.strip()
    if len(text) > 200:
        text = text[:200]
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    text = re.sub(r'[;&|`$(){}]', '', text)
    return text


def _check_rate_limit(user_id: int) -> bool:
    now = time.time()
    last = _USER_COOLDOWN.get(user_id, 0)
    if now - last < _COOLDOWN_SECONDS:
        return True
    _USER_COOLDOWN[user_id] = now
    return False


def _check_concurrent(chat_id: int) -> bool:
    now = time.time()
    _GLOBAL_SPAM[chat_id] = [t for t in _GLOBAL_SPAM.get(chat_id, []) if now - t < 30]
    if len(_GLOBAL_SPAM.get(chat_id, [])) >= _MAX_CONCURRENT:
        return True
    _GLOBAL_SPAM.setdefault(chat_id, []).append(now)
    return False


# =====================================================
# MAIN PLAY FUNCTION
# =====================================================

async def _play(client, message: Message, video: bool):
    await safe_react(client, message, config.random_emoji())
    cmd = "vplay" if video else "play"

    try:
        from MusicBangla.plugins.security import is_banned, is_url_blocked, log_action
        if is_banned(message.from_user.id):
            log_action(f"BLOCKED: banned user {message.from_user.id} tried /{cmd}")
            return
    except ImportError:
        pass

    if _check_rate_limit(message.from_user.id):
        return await message.reply_text(
            f"<b>{_COOLDOWN_SECONDS} সেকেন্ড অপেক্ষা করুন।</b>"
        )

    if _check_concurrent(message.chat.id):
        return await message.reply_text(
            "<b>একসাথে অনেক রিকোয়েস্ট!</b> কিছুক্ষণ পর চেষ্টা করুন।"
        )

    if len(message.command) < 2 and not message.reply_to_message:
        return await message.reply_text(
            f"<b>গানের নাম দাও!</b>\n\n"
            f"উদাহরণ: <code>/{cmd} tum hi ho</code>\n"
            f"Spotify/Apple Music/JioSaavn/YouTube লিংকও চলবে!\n"
            f"কিউ দেখতে: <code>/queue</code>"
        )

    raw_query = (
        " ".join(message.command[1:])
        if len(message.command) > 1
        else (message.reply_to_message.text or "")
    )

    query = _sanitize_query(raw_query)
    if not query:
        return await message.reply_text("<b>সঠিক গানের নাম দাও!</b>")

    # Handle URLs
    is_yt_url = False
    streaming_service = ""

    if query.startswith("http"):
        if re.match(
            r'https?://(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/', query
        ):
            is_yt_url = True
        else:
            streaming_service = _is_streaming_url(query)
            if not streaming_service:
                # Try generic yt-dlp download for unknown URLs
                LOGGER.info(f"Unknown URL, trying generic download: {query}")
                streaming_service = "Direct"

        try:
            from MusicBangla.plugins.security import is_url_blocked
            if is_url_blocked(query):
                return await message.reply_text("<b>এই URL ব্লক করা হয়েছে।</b>")
        except ImportError:
            pass

    requester = message.from_user.mention
    chat_id = message.chat.id

    # If something already playing, ADD TO QUEUE
    if chat_id in ACTIVE_CHATS:
        if chat_id not in QUEUES:
            QUEUES[chat_id] = deque()

        if len(QUEUES[chat_id]) >= 20:
            return await message.reply_text(
                "<b>কিউ পূর্ণ!</b> সর্বোচ্চ ২০টি গান রাখা যায়।"
            )

        QUEUES[chat_id].append((query, video, requester))
        pos = len(QUEUES[chat_id])
        icon = "🎬" if video else "🎵"
        return await message.reply_text(
            f"{icon} <b>কিউতে যোগ হয়েছে!</b>\n\n"
            f"🔢 <b>অবস্থান:</b> #{pos}\n"
            f"🔎 <b>গান:</b> <code>{query[:60]}</code>\n"
            f"🙋 <b>অনুরোধ:</b> {requester}\n\n"
            f"কিউ দেখতে: <code>/queue</code>"
        )

    # --- Nothing playing -> play now ---
    status = await message.reply_text(
        f"{config.random_search_emoji()} <b>খুঁজছি...</b>"
    )

    try:
        loop = asyncio.get_event_loop()

        assistant_ok = await ensure_assistant(chat_id)
        if not assistant_ok:
            return await status.edit(
                "<b>Assistant গ্রুপে যোগ হতে পারেনি!</b>\n"
                "Assistant manually গ্রুপে add করুন।"
            )

        search_query = query

        # For streaming service URLs, extract song name
        if streaming_service:
            await status.edit(
                f"<b>{streaming_service} লিংক থেকে গান খুঁজছি...</b>"
            )

            # Try direct yt-dlp download first (works for SoundCloud, Deezer, JioSaavn etc)
            if streaming_service not in ("Spotify", "Apple Music"):
                try:
                    direct_path, direct_info = await loop.run_in_executor(
                        None, _generic_ytdlp_download, query, video
                    )
                    if direct_path and direct_info:
                        await status.edit("🎶 <b>Voice Chat-এ যোগ হচ্ছে...</b>")
                        await asyncio.sleep(1)
                        result = await try_play_stream(chat_id, str(direct_path), video)
                        if result is True:
                            ACTIVE_CHATS[chat_id] = direct_info
                            try:
                                await status.delete()
                            except Exception:
                                pass
                            await send_now_playing(chat_id, direct_info, video, requester)
                            try:
                                await message.reply_sticker(config.random_play_sticker())
                            except Exception:
                                pass
                            return
                except Exception:
                    pass

            # Extract song name and search
            extracted = await loop.run_in_executor(
                None, _extract_song_from_url, query
            )
            if extracted:
                search_query = extracted
                LOGGER.info(f"{streaming_service} URL -> query: {search_query}")
            else:
                return await status.edit(
                    f"<b>{streaming_service} লিংক থেকে গানের তথ্য পাওয়া যায়নি!</b>\n"
                    "গানের নাম দিয়ে চেষ্টা করুন।"
                )

        # For YouTube URL, try direct download first
        if is_yt_url:
            await status.edit("<b>YouTube থেকে লোড হচ্ছে...</b>")
            yt_path = await loop.run_in_executor(
                None, _youtube_download, query, video
            )
            if yt_path:
                yt_info = await loop.run_in_executor(
                    None, _youtube_search, query
                )
                if not yt_info:
                    yt_info = {
                        "title": "YouTube", "duration": 0, "channel": "YouTube",
                        "thumb": "", "link": query, "source": "YouTube",
                    }

                await status.edit("🎶 <b>Voice Chat-এ যোগ হচ্ছে...</b>")
                await asyncio.sleep(1)
                result = await try_play_stream(chat_id, str(yt_path), video)
                if result is True:
                    ACTIVE_CHATS[chat_id] = yt_info
                    try:
                        await status.delete()
                    except Exception:
                        pass
                    await send_now_playing(chat_id, yt_info, video, requester)
                    try:
                        await message.reply_sticker(config.random_play_sticker())
                    except Exception:
                        pass
                    return

            # YT direct failed -> try Invidious for this video
            await status.edit("<b>YouTube বিকল্প উৎস থেকে চেষ্টা করছি...</b>")
            yt_info_search = await loop.run_in_executor(
                None, _youtube_search, query
            )
            if yt_info_search:
                search_query = yt_info_search.get("title", query)
            # Fall through to multi-source search

        # Multi-source search and download
        await status.edit(
            f"{config.random_download_emoji()} <b>ডাউনলোড হচ্ছে...</b>\n"
            f"🔎 <code>{search_query[:50]}</code>"
        )

        try:
            media_path, info = await asyncio.wait_for(
                loop.run_in_executor(
                    None, search_and_get_media, search_query, video
                ),
                timeout=120,
            )
        except asyncio.TimeoutError:
            return await status.edit("⏱ <b>টাইমআউট!</b> আবার চেষ্টা করুন।")
        except Exception as e:
            return await status.edit(
                f"<b>গান পাওয়া যায়নি!</b>\n<code>{str(e)[:100]}</code>\n\n"
                "অন্য গানের নাম দিয়ে চেষ্টা করুন।"
            )

        if not media_path:
            return await status.edit("<b>মিডিয়া পাওয়া যায়নি।</b>")

        source_name = info.get("source", "?")
        await status.edit(
            f"🎶 <b>Voice Chat-এ যোগ হচ্ছে...</b>\n📡 {source_name}"
        )
        await asyncio.sleep(1)

        result = await try_play_stream(chat_id, str(media_path), video)

        if result is True:
            ACTIVE_CHATS[chat_id] = info
        elif result == "NO_VC":
            return await status.edit(
                "<b>Voice Chat চালু নেই!</b>\n"
                "গ্রুপে VC শুরু করুন, তারপর <code>/play</code> দিন।"
            )
        elif result == "NO_PERM":
            return await status.edit(
                "<b>Permission নেই!</b>\n"
                "Assistant-কে admin করুন।"
            )
        else:
            return await status.edit(
                f"<b>স্ট্রিমিং ব্যর্থ!</b>\n<code>{result}</code>"
            )

        try:
            await status.delete()
        except Exception:
            pass

        await send_now_playing(chat_id, info, video, requester)

        try:
            await asyncio.sleep(0.3)
            await message.reply_sticker(config.random_play_sticker())
        except Exception:
            pass

    except Exception as e:
        LOGGER.error(f"Play error: {e}")
        import traceback
        traceback.print_exc()
        try:
            await status.edit(f"<b>ত্রুটি:</b> <code>{str(e)[:100]}</code>")
        except Exception:
            pass


# =====================================================
# CALLBACKS & COMMANDS
# =====================================================

@app.on_callback_query(filters.regex("^close_play_msg$"))
async def close_play_msg_cb(client, query):
    try:
        await query.message.delete()
    except Exception:
        await query.answer("মুছতে পারছি না!", show_alert=True)


@app.on_message(filters.command(["play", "p"]) & filters.group)
async def play_cmd(client, message: Message):
    await _play(client, message, video=False)


@app.on_message(filters.command(["vplay", "vp"]) & filters.group)
async def vplay_cmd(client, message: Message):
    await _play(client, message, video=True)


@app.on_message(filters.command(["queue", "q"]) & filters.group)
async def queue_cmd(client, message: Message):
    chat_id = message.chat.id
    current = ACTIVE_CHATS.get(chat_id)
    queue = QUEUES.get(chat_id, deque())

    if not current and not queue:
        return await message.reply_text(
            "<b>কিউ খালি!</b>\n<code>/play গানের নাম</code> দিয়ে শুরু করুন।"
        )

    text = "╭───❀ <b>🎵 MusicBangla কিউ</b> ❀───╮\n\n"

    if current:
        text += (
            f"▶️ <b>এখন বাজছে:</b>\n"
            f"   🎵 {current.get('title', '?')}\n"
            f"   ⏱ {fmt_dur(current.get('duration'))} | "
            f"📡 {current.get('source', '?')}\n\n"
        )

    if queue:
        text += f"📋 <b>কিউতে আছে ({len(queue)} টি):</b>\n"
        for i, (q, v, req) in enumerate(queue, 1):
            icon = "🎬" if v else "🎵"
            text += f"  {i}. {icon} <code>{q[:40]}</code> — {req}\n"
            if i >= 10:
                remaining = len(queue) - 10
                if remaining > 0:
                    text += f"  ... এবং আরো {remaining} টি\n"
                break
    else:
        text += "📋 কিউতে কোনো গান নেই।\n"

    text += (
        f"\n╰───❀ ✦ ❀───╯\n"
        f"➕ <code>/play গান</code> — কিউতে যোগ\n"
        f"⏭ <code>/skip</code> — পরবর্তী গান\n"
        f"🗑 <code>/clearqueue</code> — কিউ মুছুন"
    )
    await message.reply_text(text)


@app.on_message(filters.command("clearqueue") & filters.group)
async def clearqueue_cmd(client, message: Message):
    chat_id = message.chat.id
    if chat_id in QUEUES:
        count = len(QUEUES[chat_id])
        QUEUES[chat_id].clear()
        await message.reply_text(
            f"🗑 <b>{count} টি গান কিউ থেকে মুছে ফেলা হয়েছে।</b>"
        )
    else:
        await message.reply_text("<b>কিউ আগে থেকেই খালি!</b>")


# =====================================================
# COOKIE MANAGEMENT COMMANDS (owner only)
# =====================================================

@app.on_message(filters.command("refreshcookies") & filters.user(config.OWNER_ID))
async def refresh_cookies_cmd(client, message: Message):
    """Reload cookies from YT_COOKIES env var without restarting bot."""
    result = load_cookies_from_env()
    if result and _COOKIE_FILE:
        try:
            with open(_COOKIE_FILE) as f:
                lines = [l for l in f.readlines() if l.strip() and not l.startswith("#")]
            await message.reply_text(
                f"✅ <b>Cookies রিফ্রেশ হয়েছে!</b>\n\n"
                f"🍪 মোট cookies: <code>{len(lines)}</code>\n"
                f"📁 ফাইল: <code>{_COOKIE_FILE}</code>\n\n"
                f"YouTube এখন cookies সহ কাজ করবে।"
            )
        except Exception:
            await message.reply_text("✅ <b>Cookies রিফ্রেশ হয়েছে!</b>")
    else:
        await message.reply_text(
            "❌ <b>Cookies পাওয়া যায়নি!</b>\n\n"
            "Heroku Config Vars-এ <code>YT_COOKIES</code> সেট করুন।\n\n"
            "<b>কিভাবে করবেন:</b>\n"
            "1. Chrome-এ YouTube-এ login করুন\n"
            "2. <b>Get cookies.txt LOCALLY</b> extension ইন্সটল করুন\n"
            "3. youtube.com-এ গিয়ে Export করুন\n"
            "4. cookies.txt-এর সম্পূর্ণ content কপি করুন\n"
            "5. Heroku Dashboard > Settings > Config Vars\n"
            "6. <code>YT_COOKIES</code> এ paste করুন\n"
            "7. <code>/refreshcookies</code> দিন"
        )


@app.on_message(filters.command("setcookies") & filters.private & filters.user(config.OWNER_ID))
async def set_cookies_cmd(client, message: Message):
    """Set cookies directly via message (private chat only for security)."""
    global _COOKIE_FILE

    if len(message.command) < 2 and not message.reply_to_message:
        return await message.reply_text(
            "🍪 <b>Cookies সেট করতে:</b>\n\n"
            "<b>পদ্ধতি ১:</b> cookies.txt-এর content সরাসরি পাঠান:\n"
            "<code>/setcookies\n"
            ".youtube.com\tTRUE\t/\tTRUE\t...\tSID\t...</code>\n\n"
            "<b>পদ্ধতি ২:</b> cookies.txt ফাইল reply করে:\n"
            "<code>/setcookies</code>"
        )

    cookie_text = ""

    # Check if replying to a document
    if message.reply_to_message and message.reply_to_message.document:
        try:
            doc = message.reply_to_message.document
            fpath = await message.reply_to_message.download()
            with open(fpath, "r") as f:
                cookie_text = f.read()
            os.remove(fpath)
        except Exception as e:
            return await message.reply_text(f"❌ ফাইল পড়া যায়নি: {str(e)[:80]}")
    else:
        # Get from command text
        cookie_text = message.text.split(None, 1)[1] if len(message.command) > 1 else ""
        if not cookie_text and message.reply_to_message:
            cookie_text = message.reply_to_message.text or ""

    if not cookie_text or len(cookie_text) < 50:
        return await message.reply_text("❌ <b>Cookie data খুব ছোট বা খালি!</b>")

    try:
        lines = cookie_text.replace("\\n", "\n").split("\n")
        fixed = ["# Netscape HTTP Cookie File"]
        for line in lines:
            line = line.strip()
            if not line or "Netscape" in line or "HTTP Cookie" in line:
                continue
            if line.startswith("#"):
                fixed.append(line)
                continue
            fixed.append(_fix_cookie_line(line))

        cookie_count = sum(1 for l in fixed if l and not l.startswith("#"))
        if cookie_count == 0:
            return await message.reply_text("❌ <b>কোনো valid cookie পাওয়া যায়নি!</b>")

        with open("cookies.txt", "w") as f:
            f.write("\n".join(fixed) + "\n")
        _COOKIE_FILE = "cookies.txt"

        # Test the cookies with a quick YouTube check
        test_ok = False
        try:
            opts = _base_opts()
            opts["extract_flat"] = True
            opts["cookiefile"] = _COOKIE_FILE
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info("ytsearch1:test", download=False)
            test_ok = True
        except Exception:
            pass

        status = "✅ YouTube টেস্ট সফল!" if test_ok else "⚠️ YouTube টেস্ট ব্যর্থ — cookies সমস্যা থাকতে পারে"

        await message.reply_text(
            f"🍪 <b>Cookies সেট হয়েছে!</b>\n\n"
            f"📊 মোট cookies: <code>{cookie_count}</code>\n"
            f"📁 ফাইল: <code>cookies.txt</code>\n"
            f"{status}\n\n"
            f"💡 <b>টিপস:</b>\n"
            f"• Heroku-তে permanent করতে Config Vars-এ <code>YT_COOKIES</code> এও paste করুন\n"
            f"• Cookies expire হলে আবার <code>/setcookies</code> দিন"
        )

        # Delete the message containing cookies for security
        try:
            await message.delete()
        except Exception:
            pass

    except Exception as e:
        await message.reply_text(f"❌ Cookie সেট করতে সমস্যা: <code>{str(e)[:80]}</code>")


@app.on_message(filters.command("cookiestatus") & filters.user(config.OWNER_ID))
async def cookie_status_cmd(client, message: Message):
    """Check current cookie status."""
    if _COOKIE_FILE and os.path.exists(_COOKIE_FILE):
        try:
            with open(_COOKIE_FILE) as f:
                content = f.read()
            lines = [l for l in content.split("\n") if l.strip() and not l.startswith("#")]
            fsize = os.path.getsize(_COOKIE_FILE)

            # Check if cookies are YouTube cookies
            yt_cookies = sum(1 for l in lines if ".youtube.com" in l or ".google.com" in l)

            # Test cookies
            test_ok = False
            try:
                opts = _base_opts()
                opts["extract_flat"] = True
                opts["cookiefile"] = _COOKIE_FILE
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.extract_info("ytsearch1:test", download=False)
                test_ok = True
            except Exception:
                pass

            status_icon = "🟢" if test_ok else "🔴"
            status_text = "কাজ করছে" if test_ok else "কাজ করছে না (expired/invalid)"

            await message.reply_text(
                f"🍪 <b>Cookie Status</b>\n\n"
                f"📁 ফাইল: <code>{_COOKIE_FILE}</code>\n"
                f"📊 মোট entries: <code>{len(lines)}</code>\n"
                f"🌐 YouTube cookies: <code>{yt_cookies}</code>\n"
                f"💾 সাইজ: <code>{fsize}</code> bytes\n"
                f"{status_icon} Status: <b>{status_text}</b>\n\n"
                f"🔄 রিফ্রেশ: <code>/refreshcookies</code>\n"
                f"📝 নতুন সেট: <code>/setcookies</code>"
            )
        except Exception as e:
            await message.reply_text(f"❌ Cookie চেক করতে সমস্যা: {str(e)[:80]}")
    else:
        await message.reply_text(
            "🍪 <b>কোনো cookie সেট নেই!</b>\n\n"
            "📝 সেট করুন: <code>/setcookies</code> (private chat-এ)\n"
            "🔄 অথবা Heroku Config Vars-এ <code>YT_COOKIES</code> সেট করে <code>/refreshcookies</code> দিন"
        )
