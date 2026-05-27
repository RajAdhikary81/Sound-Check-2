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
    rows = []
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
    rows.append([
        InlineKeyboardButton("📢 চ্যানেল", url=config.SUPPORT_CHANNEL),
        InlineKeyboardButton("💬 সাপোর্ট", url=config.SUPPORT_GROUP),
    ])
    rows.append([
        InlineKeyboardButton(
            "👨‍💻 মালিক",
            url=f"https://t.me/{config.OWNER_USERNAME}",
        ),
        InlineKeyboardButton("❌ বন্ধ করো", callback_data="close_play_msg"),
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
        # NO postprocessors — just download raw file

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"scsearch3:{query}", download=False)

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
# SOURCE 2: YOUTUBE (via yt-dlp — multiple clients)
# =====================================================

def _youtube_search(query: str):
    """Search YouTube via yt-dlp flat search."""
    try:
        opts = _base_opts()
        opts["extract_flat"] = True
        if _COOKIE_FILE:
            opts["cookiefile"] = _COOKIE_FILE

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)

            entries = []
            if info and info.get("_type") == "playlist" and info.get("entries"):
                entries = list(info["entries"])

            if not entries:
                return None

            v = entries[0]
            vid = v.get("id") or v.get("url", "")
            return {
                "title": v.get("title", "Unknown"),
                "duration": int(v.get("duration", 0) or 0),
                "link": f"https://www.youtube.com/watch?v={vid}",
                "thumb": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                "channel": v.get("channel", "") or v.get("uploader", "YouTube"),
                "id": vid,
                "source": "YouTube",
            }
    except Exception as e:
        LOGGER.error(f"YT search error: {e}")
        return None


def _youtube_download(url: str, video: bool) -> str:
    """Download from YouTube. Try cookies first, then different clients."""
    cleanup_downloads()
    suffix = "_v" if video else ""
    outtmpl = f"downloads/yt_%(id)s{suffix}.%(ext)s"
    fmt = "best[height<=480]/best" if video else "bestaudio/best"

    # Build strategy list
    strategies = []
    if _COOKIE_FILE:
        strategies.append((_COOKIE_FILE, None, "cookies"))
        strategies.append((_COOKIE_FILE, ["web"], "cookies+web"))
    strategies.append((None, ["mweb"], "mweb"))
    strategies.append((None, ["android"], "android"))
    strategies.append((None, None, "default"))

    for cookie, player_client, desc in strategies:
        opts = _base_opts()
        opts["format"] = fmt
        opts["outtmpl"] = outtmpl
        if cookie:
            opts["cookiefile"] = cookie
        if player_client:
            opts["extractor_args"] = {"youtube": {"player_client": player_client}}

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
                    return fname
        except Exception as e:
            LOGGER.warning(f"YT [{desc}]: {str(e)[:80]}")
        time.sleep(0.5)

    return None


# =====================================================
# SOURCE 3: BANDCAMP (via yt-dlp)
# =====================================================

def _bandcamp_search_and_download(query: str, video: bool):
    """Search Bandcamp via yt-dlp."""
    LOGGER.info(f"Bandcamp search: {query}")
    cleanup_downloads()
    try:
        opts = _base_opts()
        opts["outtmpl"] = "downloads/bc_%(id)s.%(ext)s"
        opts["format"] = "best"

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"bcsearch:{query}", download=True)

            if not info:
                return None, None

            # Handle playlist result
            if info.get("_type") == "playlist" and info.get("entries"):
                entries = list(info["entries"])
                if not entries:
                    return None, None
                info = entries[0]
                if not info:
                    return None, None
                # Re-download the specific track
                url = info.get("webpage_url") or info.get("url")
                if url:
                    info = ydl.extract_info(url, download=True)

            track_id = info.get("id", "unknown")
            local_path = _find_downloaded_file("bc_", track_id, ydl, info)

            if local_path and os.path.getsize(local_path) > 5000:
                LOGGER.info(f"Bandcamp OK: {info.get('title')} -> {local_path}")
                return local_path, {
                    "title": info.get("title", "Unknown"),
                    "duration": int(info.get("duration", 0) or 0),
                    "channel": info.get("uploader", info.get("artist", "Bandcamp")),
                    "thumb": info.get("thumbnail", ""),
                    "link": info.get("webpage_url", ""),
                    "source": "Bandcamp",
                }

    except Exception as e:
        LOGGER.warning(f"Bandcamp error: {str(e)[:60]}")

    return None, None


# =====================================================
# URL HANDLING: Spotify, Apple Music, etc.
# =====================================================

def _extract_song_from_url(url: str) -> str:
    """Extract song name from streaming service URL."""
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
# MASTER SEARCH: yt-dlp only — no external APIs
# =====================================================

def search_and_get_media(query: str, video: bool):
    """
    Multi-source via yt-dlp only (no external API dependencies):
      1. SoundCloud (most reliable, never IP-blocked)
      2. YouTube (cookies + mweb/android clients)
      3. Bandcamp (indie/alternative music)
    All sources use yt-dlp — works on any platform (Heroku/VPS/local).
    """
    errors = []

    # === Source 1: SoundCloud ===
    LOGGER.info("=== Source 1: SoundCloud ===")
    try:
        path, info = _soundcloud_search_and_download(query, video)
        if path and info:
            return path, info
        errors.append("SoundCloud: no results")
    except Exception as e:
        errors.append(f"SC: {str(e)[:50]}")

    # === Source 2: YouTube ===
    LOGGER.info("=== Source 2: YouTube ===")
    try:
        yt_info = _youtube_search(query)
        if yt_info:
            path = _youtube_download(yt_info["link"], video)
            if path:
                return path, yt_info
            errors.append("YouTube: download failed")
        else:
            errors.append("YouTube: search failed")
    except Exception as e:
        errors.append(f"YT: {str(e)[:50]}")

    # === Source 3: Bandcamp ===
    LOGGER.info("=== Source 3: Bandcamp ===")
    try:
        path, info = _bandcamp_search_and_download(query, video)
        if path and info:
            return path, info
        errors.append("Bandcamp: no results")
    except Exception as e:
        errors.append(f"BC: {str(e)[:50]}")

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
# NOW-PLAYING message
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

    # --- Nothing playing -> play now ---
    status = await message.reply_text(
        "<b>খুঁজছি...</b> 🔍"
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

            # Direct YT download failed -> extract title and use multi-search
            yt_info = await loop.run_in_executor(
                None, _youtube_search, query
            )
            if yt_info:
                search_query = yt_info.get("title", query)

        # Multi-source search and download
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
