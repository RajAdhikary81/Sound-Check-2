import os
import asyncio
import time
import re
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

if os.environ.get("YT_COOKIES"):
    try:
        raw = os.environ["YT_COOKIES"].replace("\\n", "\n")
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
    except Exception as e:
        LOGGER.error(f"Cookie write error: {e}")
elif os.path.exists("cookies.txt"):
    _COOKIE_FILE = "cookies.txt"


# =====================================================
# YT-DLP BASE OPTIONS
# =====================================================

def _base_opts():
    return {
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
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }


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
# INLINE BUTTONS for now-playing message
# =====================================================

def _play_buttons(song_link: str = "") -> InlineKeyboardMarkup:
    """Build inline buttons for the now-playing message."""
    rows = []

    # Row 1: Song link (if available) + Support
    row1 = []
    if song_link and song_link.startswith("http"):
        row1.append(InlineKeyboardButton("🔗 গান দেখো", url=song_link))
    row1.append(
        InlineKeyboardButton(
            "➕ গ্রুপে যোগ করো",
            url="https://t.me/MusicBanglaBot?startgroup=true",
        )
    )
    rows.append(row1)

    # Row 2: Support group & channel
    rows.append([
        InlineKeyboardButton("📢 চ্যানেল", url=config.SUPPORT_CHANNEL),
        InlineKeyboardButton("💬 সাপোর্ট", url=config.SUPPORT_GROUP),
    ])

    # Row 3: Owner & close
    rows.append([
        InlineKeyboardButton(
            "👨‍💻 মালিক",
            url=f"https://t.me/{config.OWNER_USERNAME}",
        ),
        InlineKeyboardButton("❌ বন্ধ করো", callback_data="close_play_msg"),
    ])

    return InlineKeyboardMarkup(rows)


# =====================================================
# SOURCE 1: SOUNDCLOUD (Primary — most reliable)
# =====================================================

def _soundcloud_search_and_get(query: str, video: bool):
    """Search SoundCloud via yt-dlp and download."""
    LOGGER.info(f"SoundCloud search: {query}")
    cleanup_downloads()

    try:
        # Step 1: Search with more results for better matching
        search_opts = _base_opts()
        with yt_dlp.YoutubeDL(search_opts) as ydl:
            info = ydl.extract_info(f"scsearch5:{query}", download=False)

            entries = []
            if info.get("_type") == "playlist" and info.get("entries"):
                entries = list(info["entries"])

            if not entries:
                LOGGER.warning("SoundCloud: no results")
                return None, None

            # Smart matching: filter out slowed/reverb/remix unless asked
            best = _pick_best_match(entries, query)
            if not best:
                best = entries[0]

            webpage_url = best.get("webpage_url") or best.get("url")
            if not webpage_url:
                return None, None

        # Step 2: Download with NEW YoutubeDL instance + best quality
        LOGGER.info(f"SoundCloud: downloading '{best.get('title')}'")
        dl_opts = _base_opts()
        dl_opts["outtmpl"] = "downloads/sc_%(id)s.%(ext)s"
        # SoundCloud: use bestaudio which auto-selects best available
        dl_opts["format"] = "bestaudio/best"
        dl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "best",
            "preferredquality": "0",
        }]

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
                fsize = os.path.getsize(local_path)
                LOGGER.info(f"SoundCloud OK: {title} -> {local_path} ({fsize} bytes)")
                return local_path, {
                    "title": title,
                    "duration": int(duration) if duration else 0,
                    "channel": uploader,
                    "thumb": thumb,
                    "link": webpage,
                    "source": "SoundCloud",
                }

        LOGGER.warning("SoundCloud: file not found or too small")
        return None, None

    except Exception as e:
        LOGGER.error(f"SoundCloud error: {e}")
        return None, None


def _pick_best_match(entries, query):
    """Pick the entry whose title best matches the query.
    Penalizes slowed/reverb/remix versions unless query asks for them."""
    query_lower = query.lower().strip()
    query_words = set(query_lower.split())

    # Check if user specifically wants remix/slowed
    wants_remix = any(w in query_lower for w in ["remix", "slowed", "reverb", "lofi", "lo-fi"])

    best_entry = None
    best_score = -999

    for entry in entries:
        title = (entry.get("title") or "").lower()
        if not title:
            continue

        title_words = set(title.split())
        # Word overlap score
        overlap = len(query_words & title_words)
        # Bonus if query is substring of title or vice versa
        substring_bonus = 3 if query_lower in title else 0
        substring_bonus += 2 if title in query_lower else 0

        # Heavy penalty for slowed/reverb/remix unless user asked for it
        bad_words = ["slowed", "reverb", "reverbed", "lofi", "lo-fi",
                     "8d", "bass boosted", "nightcore"]
        penalty = 0
        if not wants_remix:
            for bw in bad_words:
                if bw in title and bw not in query_lower:
                    penalty += 5

        # Penalty for very different length
        len_penalty = abs(len(title) - len(query_lower)) / max(len(query_lower), 1) * 0.3

        # Bonus for having original/official in title
        official_bonus = 1 if any(w in title for w in ["original", "official"]) else 0

        # Duration penalty: skip very short clips (<60s)
        dur = entry.get("duration", 0) or 0
        short_penalty = 3 if dur and dur < 60 else 0

        score = overlap + substring_bonus + official_bonus - penalty - len_penalty - short_penalty

        if score > best_score:
            best_score = score
            best_entry = entry

    return best_entry


def _find_downloaded_file(prefix, track_id, ydl=None, info=None):
    """Find downloaded file by prefix + id or ydl filename."""
    for ext in [".m4a", ".mp3", ".webm", ".opus", ".ogg", ".wav", ".mp4", ".mkv"]:
        candidate = f"downloads/{prefix}{track_id}{ext}"
        if os.path.exists(candidate):
            return candidate

    if ydl and info:
        try:
            fname = ydl.prepare_filename(info)
            base = os.path.splitext(fname)[0]
            for ext in [".m4a", ".mp3", ".webm", ".opus", ".ogg", ".mp4"]:
                if os.path.exists(base + ext):
                    return base + ext
            if os.path.exists(fname):
                return fname
        except Exception:
            pass

    # Last resort: any recent file
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
# SOURCE 2: YOUTUBE (with web/mweb/android clients)
# =====================================================

def _youtube_search_sync(query: str):
    """Search YouTube using yt-dlp flat search (doesn't need auth)."""
    try:
        opts = _base_opts()
        opts["extract_flat"] = True
        if _COOKIE_FILE:
            opts["cookiefile"] = _COOKIE_FILE

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)

            entries = []
            if info.get("_type") == "playlist" and info.get("entries"):
                entries = list(info["entries"])

            if not entries:
                return None

            v = entries[0]
            vid = v.get("id") or v.get("url", "")
            title = v.get("title", "Unknown")
            duration = v.get("duration", 0) or 0
            thumb = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
            channel = v.get("channel", "") or v.get("uploader", "YouTube")

            return {
                "title": title,
                "duration": int(duration) if duration else 0,
                "link": f"https://www.youtube.com/watch?v={vid}",
                "thumb": thumb,
                "channel": channel,
                "id": vid,
                "source": "YouTube",
            }
    except Exception as e:
        LOGGER.error(f"YT search error: {e}")
        return None


def _youtube_download(url: str, video: bool) -> str:
    """Download from YouTube using multiple fallback strategies."""
    cleanup_downloads()
    suffix = "_v" if video else ""
    outtmpl = f"downloads/yt_%(id)s{suffix}.%(ext)s"

    # Valid yt-dlp player_clients: web, web_embedded, android, ios, tv, mweb
    # android_vr removed in recent yt-dlp versions
    if video:
        strategies = [
            ("18/best[height<=480][ext=mp4]/best[height<=480]/best", ["web"], "yt-v:web"),
            ("18/best[height<=480]/best", ["mweb"], "yt-v:mweb"),
            ("18/best", ["android"], "yt-v:android"),
            ("18/best", None, "yt-v:default"),
        ]
    else:
        strategies = [
            ("bestaudio[ext=m4a]/bestaudio/best", ["web"], "yt:web"),
            ("bestaudio/best", ["mweb"], "yt:mweb"),
            ("bestaudio/best", ["android"], "yt:android"),
            ("bestaudio/best", None, "yt:default"),
        ]

    for fmt_str, player_client, desc in strategies:
        opts = _base_opts()
        opts["format"] = fmt_str
        opts["outtmpl"] = outtmpl
        if _COOKIE_FILE:
            opts["cookiefile"] = _COOKIE_FILE
        if player_client:
            opts["extractor_args"] = {"youtube": {"player_client": player_client}}

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                fname = ydl.prepare_filename(info)
                base = os.path.splitext(fname)[0]
                for ext in [".m4a", ".mp3", ".webm", ".opus", ".ogg", ".mp4", ".mkv"]:
                    if os.path.exists(base + ext):
                        fpath = base + ext
                        if os.path.getsize(fpath) > 5000:
                            LOGGER.info(f"YT download OK [{desc}]: {fpath}")
                            return fpath
                if os.path.exists(fname) and os.path.getsize(fname) > 5000:
                    return fname
        except Exception as e:
            LOGGER.warning(f"YT download [{desc}]: {str(e)[:80]}")
        time.sleep(1)

    return None


# =====================================================
# SOURCE 3: PIPED API (YouTube proxy — no blocks)
# =====================================================

PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.adminforge.de",
    "https://pipedapi.in.projectsegfau.lt",
]


def _piped_search_and_get(query: str, video: bool):
    """Search and download via Piped API (YouTube proxy)."""
    LOGGER.info(f"Piped search: {query}")
    cleanup_downloads()

    for base_url in PIPED_INSTANCES:
        try:
            with httpx.Client(timeout=20, follow_redirects=True) as client:
                # Search
                resp = client.get(
                    f"{base_url}/search",
                    params={"q": query, "filter": "music_songs"}
                )
                if resp.status_code != 200:
                    continue

                data = resp.json()
                items = data.get("items", [])
                if not items:
                    continue

                # Pick first video result
                item = None
                for it in items:
                    if it.get("type") == "stream":
                        item = it
                        break
                if not item:
                    item = items[0]

                vid_url = item.get("url", "")
                if not vid_url:
                    continue

                # Get stream info
                vid_id = vid_url.split("?v=")[-1] if "?v=" in vid_url else vid_url.strip("/").split("/")[-1]
                stream_resp = client.get(f"{base_url}/streams/{vid_id}")
                if stream_resp.status_code != 200:
                    continue

                stream_data = stream_resp.json()
                title = stream_data.get("title", item.get("title", "Unknown"))
                duration = stream_data.get("duration", 0)
                uploader = stream_data.get("uploader", "YouTube")
                thumb = stream_data.get("thumbnailUrl", "")

                # Get audio/video stream URL
                stream_url = None
                if video:
                    # Get video stream with audio
                    for vs in stream_data.get("videoStreams", []):
                        if vs.get("videoOnly", True):
                            continue
                        stream_url = vs.get("url")
                        if stream_url:
                            break

                if not stream_url:
                    # Get best audio stream
                    audio_streams = stream_data.get("audioStreams", [])
                    if audio_streams:
                        # Sort by bitrate, pick highest
                        audio_streams.sort(
                            key=lambda x: x.get("bitrate", 0), reverse=True
                        )
                        stream_url = audio_streams[0].get("url")

                if not stream_url:
                    continue

                # Download using httpx
                ext = ".mp4" if video else ".m4a"
                local_path = f"downloads/piped_{vid_id}{ext}"

                with open(local_path, "wb") as f:
                    with client.stream("GET", stream_url, follow_redirects=True) as dl_resp:
                        if dl_resp.status_code != 200:
                            continue
                        for chunk in dl_resp.iter_bytes(65536):
                            f.write(chunk)

                if os.path.exists(local_path) and os.path.getsize(local_path) > 5000:
                    LOGGER.info(f"Piped OK: {title} -> {local_path}")
                    return local_path, {
                        "title": title,
                        "duration": int(duration) if duration else 0,
                        "channel": uploader,
                        "thumb": thumb,
                        "link": f"https://www.youtube.com/watch?v={vid_id}",
                        "source": "Piped (YouTube)",
                    }

        except Exception as e:
            LOGGER.warning(f"Piped [{base_url}]: {str(e)[:60]}")
            continue

    return None, None


# =====================================================
# SOURCE 4: JIOSAAVN API (Indian music — free)
# =====================================================

JIOSAAVN_API = "https://saavn.dev/api"


def _jiosaavn_search_and_get(query: str, video: bool):
    """Search and download from JioSaavn (great for Bollywood/Bengali)."""
    LOGGER.info(f"JioSaavn search: {query}")
    cleanup_downloads()

    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            # Search
            resp = client.get(
                f"{JIOSAAVN_API}/search/songs",
                params={"query": query, "limit": 5}
            )
            if resp.status_code != 200:
                return None, None

            data = resp.json()
            results = data.get("data", {}).get("results", [])
            if not results:
                return None, None

            # Pick best match
            song = results[0]
            song_id = song.get("id", "")
            title = song.get("name", "Unknown")
            duration = song.get("duration", 0)
            artists = ", ".join(
                a.get("name", "") for a in song.get("artists", {}).get("primary", [])
            ) or song.get("label", "JioSaavn")

            # Get download URLs
            dl_urls = song.get("downloadUrl", [])
            if not dl_urls:
                # Try getting song details for download URLs
                detail_resp = client.get(
                    f"{JIOSAAVN_API}/songs/{song_id}"
                )
                if detail_resp.status_code == 200:
                    detail = detail_resp.json()
                    dl_urls = detail.get("data", [{}])[0].get("downloadUrl", []) if isinstance(detail.get("data"), list) else detail.get("data", {}).get("downloadUrl", [])

            if not dl_urls:
                return None, None

            # Pick highest quality
            download_url = None
            for dl in reversed(dl_urls):  # reversed = highest quality first
                url = dl.get("url", "") or dl.get("link", "")
                if url:
                    download_url = url
                    break

            if not download_url:
                return None, None

            # Get thumbnail
            images = song.get("image", [])
            thumb = ""
            if images and isinstance(images, list):
                thumb = images[-1].get("url", "") or images[-1].get("link", "")
            elif isinstance(images, str):
                thumb = images

            song_url = song.get("url", "")

            # Download the audio file
            local_path = f"downloads/jiosaavn_{song_id}.mp3"
            dl_resp = client.get(download_url, follow_redirects=True)
            if dl_resp.status_code == 200 and len(dl_resp.content) > 5000:
                with open(local_path, "wb") as f:
                    f.write(dl_resp.content)

                LOGGER.info(f"JioSaavn OK: {title} -> {local_path}")
                return local_path, {
                    "title": title,
                    "duration": int(duration) if duration else 0,
                    "channel": artists,
                    "thumb": thumb,
                    "link": song_url or f"https://www.jiosaavn.com/song/{song_id}",
                    "source": "JioSaavn",
                }

    except Exception as e:
        LOGGER.error(f"JioSaavn error: {e}")

    return None, None


# =====================================================
# SPOTIFY / APPLE MUSIC / OTHER URLs -> song name
# =====================================================

def _extract_song_from_url(url: str) -> str:
    """Extract song name from streaming service URL."""
    # Try yt-dlp extraction
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

    # Fallback: HTTP page title
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
                                " - Wynk Music", " | Wynk"]:
                        raw = raw.replace(suf, "")
                    return raw.strip()
    except Exception:
        pass

    return ""


def _is_streaming_url(url: str) -> str:
    """Check if URL is from a known streaming service."""
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
# MASTER SEARCH: multi-source fallback
# =====================================================

def search_and_get_media(query: str, video: bool):
    """
    Multi-source fallback (4 layers):
      1. JioSaavn (best for Bangla/Bollywood, no IP blocks)
      2. SoundCloud (reliable, no IP blocks)
      3. YouTube via yt-dlp (needs cookies sometimes)
      4. Piped API (YouTube proxy, no blocks)
    Returns (local_file_path, info_dict) or raises.
    """
    errors = []

    # === Source 1: JioSaavn (best for Indian/Bangla music) ===
    LOGGER.info("=== Source 1: JioSaavn ===")
    try:
        path, info = _jiosaavn_search_and_get(query, video)
        if path and info:
            return path, info
        errors.append("JioSaavn: no results")
    except Exception as e:
        errors.append(f"JioSaavn: {str(e)[:50]}")

    # === Source 2: SoundCloud ===
    LOGGER.info("=== Source 2: SoundCloud ===")
    try:
        path, info = _soundcloud_search_and_get(query, video)
        if path and info:
            return path, info
        errors.append("SoundCloud: no results")
    except Exception as e:
        errors.append(f"SC: {str(e)[:50]}")

    # === Source 3: YouTube (yt-dlp) ===
    LOGGER.info("=== Source 3: YouTube ===")
    try:
        yt_info = _youtube_search_sync(query)
        if yt_info:
            path = _youtube_download(yt_info["link"], video)
            if path:
                return path, yt_info
            errors.append("YouTube: download failed")
        else:
            errors.append("YouTube: search failed")
    except Exception as e:
        errors.append(f"YT: {str(e)[:50]}")

    # === Source 4: Piped API (YouTube proxy) ===
    LOGGER.info("=== Source 4: Piped API ===")
    try:
        path, info = _piped_search_and_get(query, video)
        if path and info:
            return path, info
        errors.append("Piped: no results")
    except Exception as e:
        errors.append(f"Piped: {str(e)[:50]}")

    raise Exception(f"All sources failed: {'; '.join(errors)}")


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
        stream = MediaStream(media_path, video_flags=MediaStream.Flags.AUTO_DETECT)
    else:
        stream = MediaStream(media_path, video_flags=MediaStream.Flags.IGNORE)

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
            else:
                if attempt < max_retries:
                    await asyncio.sleep(3)
                    continue
                return f"ERROR: {str(e)[:100]}"

    return f"FAILED: {str(last_error)[:100]}"


# =====================================================
# NOW-PLAYING message builder
# =====================================================

def _build_now_playing(info: dict, video: bool, requester: str,
                       queue_len: int = 0) -> str:
    source_name = info.get("source", "?")
    icon = "🎬" if video else "🎵"
    mode = "ভিডিও" if video else "অডিও"
    caption = (
        f"╭─────────────────────╮\n"
        f"  {icon} <b>এখন {mode} বাজছে</b>\n"
        f"╰─────────────────────╯\n\n"
        f"🎵 <b>শিরোনাম:</b> {info.get('title', '?')}\n"
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
    """Send the now-playing message with thumbnail + inline buttons."""
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
# QUEUE: auto-play next song when current ends
# =====================================================

async def play_next_in_queue(chat_id: int):
    """Play next song from queue."""
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
        media_path, info = await loop.run_in_executor(
            None, search_and_get_media, next_query, next_video
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
    """Auto-play next song when current one ends."""
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
            f"Spotify/Apple Music/JioSaavn লিংকও চলবে!\n"
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
                return await message.reply_text(
                    "<b>এই URL সাপোর্টেড নয়!</b>\n\n"
                    "সাপোর্টেড: YouTube, Spotify, Apple Music, JioSaavn, "
                    "Gaana, SoundCloud, Deezer, Tidal, Amazon Music, Resso"
                )

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

    # --- Nothing playing → play now ---
    status = await message.reply_text(
        "<b>খুঁজছি...</b> (JioSaavn → SoundCloud → YouTube → Piped)"
    )

    try:
        loop = asyncio.get_event_loop()

        # Ensure assistant is in chat
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
            await status.edit("<b>YouTube লিংক থেকে লোড হচ্ছে...</b>")
            yt_path = await loop.run_in_executor(
                None, _youtube_download, query, video
            )
            if yt_path:
                yt_info = await loop.run_in_executor(
                    None, _youtube_search_sync, query
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

            # Direct download failed → extract title and search SoundCloud
            yt_info = await loop.run_in_executor(
                None, _youtube_search_sync, query
            )
            if yt_info:
                search_query = yt_info.get("title", query)

        # Search and download from all sources
        await status.edit(
            f"📥 <b>ডাউনলোড হচ্ছে...</b>\n"
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
                f"<b>সব সোর্স ব্যর্থ!</b>\n<code>{str(e)[:100]}</code>\n\n"
                "অন্য গানের নাম দিয়ে চেষ্টা করুন।"
            )

        if not media_path:
            return await status.edit("<b>মিডিয়া পাওয়া যায়নি।</b>")

        # Play
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

        # Success
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
# CALLBACK: close play message
# =====================================================

@app.on_callback_query(filters.regex("^close_play_msg$"))
async def close_play_msg_cb(client, query):
    try:
        await query.message.delete()
    except Exception:
        await query.answer("মুছতে পারছি না!", show_alert=True)


# =====================================================
# COMMANDS
# =====================================================

@app.on_message(filters.command(["play", "p"]) & filters.group)
async def play_cmd(client, message: Message):
    await _play(client, message, video=False)


@app.on_message(filters.command(["vplay", "vp"]) & filters.group)
async def vplay_cmd(client, message: Message):
    await _play(client, message, video=True)


@app.on_message(filters.command(["queue", "q"]) & filters.group)
async def queue_cmd(client, message: Message):
    """Show current queue."""
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
