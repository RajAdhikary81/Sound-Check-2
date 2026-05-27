import os
import asyncio
import time
import re
import yt_dlp
import httpx
from collections import deque
from pyrogram import filters
from pyrogram.types import Message
from pytgcalls.types import MediaStream

import config
from MusicBangla import app, assistant, calls, LOGGER


os.makedirs("downloads", exist_ok=True)

# =====================================================
# QUEUE SYSTEM — per-chat song queue + auto-play next
# =====================================================

ACTIVE_CHATS = {}   # chat_id -> current song info
QUEUES = {}         # chat_id -> deque of (query, video, requester_mention)

# --- Rate limiting & flood protection ---
_USER_COOLDOWN = {}
_COOLDOWN_SECONDS = 5
_GLOBAL_SPAM = {}
_MAX_CONCURRENT = 3


# --- Cookies (for YouTube fallback) ---
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
        "socket_timeout": 20,
        "retries": 3,
        "fragment_retries": 3,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "no_check_formats": True,
        "check_formats": False,
        "source_address": "0.0.0.0",
        "format_sort": ["abr", "asr"],
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
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
# SOURCE 1: SOUNDCLOUD (Primary — works on Heroku)
# =====================================================

def _soundcloud_search_and_get(query: str, video: bool):
    """
    Search SoundCloud via yt-dlp scsearch and DOWNLOAD the file.
    For video mode, downloads with video if available.
    """
    LOGGER.info(f"SoundCloud search: {query}")
    cleanup_downloads()

    opts = _base_opts()
    if video:
        # SoundCloud rarely has video, but try best format
        opts["format"] = "best"
    else:
        opts["format"] = "http_mp3_0_0/bestaudio/best"
    opts["default_search"] = "scsearch3"  # Get 3 results for better matching
    opts["outtmpl"] = "downloads/sc_%(id)s.%(ext)s"

    if not video:
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }]

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"scsearch3:{query}", download=False)

            # scsearch returns a playlist with entries
            entries = []
            if info.get("_type") == "playlist" and info.get("entries"):
                entries = list(info["entries"])

            if not entries:
                LOGGER.warning("SoundCloud: no results")
                return None, None

            # Pick best matching result
            best = _pick_best_match(entries, query)
            if not best:
                best = entries[0]

            # Now download the chosen track
            LOGGER.info(f"SoundCloud: downloading '{best.get('title')}'")
            dl_opts = _base_opts()
            if video:
                dl_opts["format"] = "best"
            else:
                dl_opts["format"] = "http_mp3_0_0/bestaudio/best"
                dl_opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "128",
                }]
            dl_opts["outtmpl"] = "downloads/sc_%(id)s.%(ext)s"

            webpage_url = best.get("webpage_url") or best.get("url")
            if not webpage_url:
                return None, None

            dl_info = ydl.extract_info(webpage_url, download=True)

            title = dl_info.get("title", best.get("title", "Unknown"))
            duration = dl_info.get("duration", best.get("duration", 0))
            uploader = dl_info.get("uploader", best.get("uploader", "SoundCloud"))
            thumb = dl_info.get("thumbnail", best.get("thumbnail", ""))
            webpage = dl_info.get("webpage_url", webpage_url)

            # Find the downloaded file
            track_id = dl_info.get("id", best.get("id", "unknown"))
            local_path = _find_downloaded_file("sc_", track_id, ydl, dl_info)

            if local_path:
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

            LOGGER.warning("SoundCloud: download succeeded but file not found")
            return None, None

    except Exception as e:
        LOGGER.error(f"SoundCloud error: {e}")
        return None, None


def _pick_best_match(entries, query):
    """Pick the entry whose title best matches the query."""
    query_lower = query.lower().strip()
    query_words = set(query_lower.split())

    best_entry = None
    best_score = -1

    for entry in entries:
        title = (entry.get("title") or "").lower()
        if not title:
            continue

        title_words = set(title.split())
        # Word overlap score
        overlap = len(query_words & title_words)
        # Bonus if query is substring of title or vice versa
        substring_bonus = 2 if query_lower in title or title in query_lower else 0
        # Penalty for very short or very long titles compared to query
        len_penalty = abs(len(title) - len(query_lower)) / max(len(query_lower), 1)
        score = overlap + substring_bonus - (len_penalty * 0.1)

        if score > best_score:
            best_score = score
            best_entry = entry

    return best_entry


def _find_downloaded_file(prefix, track_id, ydl=None, info=None):
    """Find downloaded file by prefix + id or ydl filename."""
    for ext in [".mp3", ".m4a", ".webm", ".opus", ".ogg", ".wav", ".mp4", ".mkv"]:
        candidate = f"downloads/{prefix}{track_id}{ext}"
        if os.path.exists(candidate):
            return candidate

    if ydl and info:
        try:
            fname = ydl.prepare_filename(info)
            base = os.path.splitext(fname)[0]
            for ext in [".mp3", ".m4a", ".webm", ".opus", ".ogg", ".mp4"]:
                if os.path.exists(base + ext):
                    return base + ext
            if os.path.exists(fname):
                return fname
        except Exception:
            pass

    # Last resort: any file with prefix
    try:
        for f in sorted(os.listdir("downloads"), key=lambda x: os.path.getmtime(os.path.join("downloads", x)), reverse=True):
            if f.startswith(prefix):
                return os.path.join("downloads", f)
    except Exception:
        pass

    return None


# =====================================================
# SOURCE 2: JIOSAAVN API (Secondary — Indian music)
# =====================================================

_JIOSAAVN_APIS = [
    "https://jiosaavn-api.vercel.app",
    "https://jiosaavn-api-v3.vercel.app",
]


def _jiosaavn_search_and_get(query: str, video: bool):
    """Search JioSaavn via public API and download the track."""
    LOGGER.info(f"JioSaavn search: {query}")

    for api_base in _JIOSAAVN_APIS:
        try:
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                resp = client.get(f"{api_base}/search", params={"query": query})
                if resp.status_code != 200:
                    continue

                data = resp.json()
                results = data.get("results", data.get("data", []))
                if not results or not isinstance(results, list):
                    continue

                song = results[0]
                song_id = song.get("id", "")
                title = song.get("title", song.get("name", "Unknown"))
                if not song_id:
                    continue

                resp2 = client.get(f"{api_base}/song", params={"id": song_id})
                if resp2.status_code != 200:
                    continue

                song_data = resp2.json()
                media_urls = song_data.get("media_urls", {})
                stream_url = None
                for quality in ["320_KBPS", "160_KBPS", "96_KBPS"]:
                    if media_urls.get(quality):
                        stream_url = media_urls[quality]
                        break
                if not stream_url:
                    stream_url = song_data.get("media_url", "")
                if not stream_url:
                    continue

                duration_str = song_data.get("duration", song_data.get("more_info", {}).get("duration", "0"))
                try:
                    duration = int(duration_str)
                except (ValueError, TypeError):
                    duration = 0

                artist = (
                    song_data.get("more_info", {}).get("singers", "")
                    or song_data.get("subtitle", "")
                    or "JioSaavn"
                )
                image = song_data.get("image", "")
                if isinstance(image, list) and image:
                    image = image[-1].get("link", "") if isinstance(image[-1], dict) else image[-1]

                local_path = f"downloads/jiosaavn_{song_id}.mp4"
                try:
                    dl_resp = client.get(stream_url, timeout=30)
                    if dl_resp.status_code == 200 and len(dl_resp.content) > 1000:
                        with open(local_path, "wb") as f:
                            f.write(dl_resp.content)
                        LOGGER.info(f"JioSaavn OK: {title} ({len(dl_resp.content)} bytes)")
                        return local_path, {
                            "title": title,
                            "duration": duration,
                            "channel": artist,
                            "thumb": image,
                            "link": song_data.get("perma_url", ""),
                            "source": "JioSaavn",
                        }
                except Exception as e:
                    LOGGER.warning(f"JioSaavn download error: {str(e)[:60]}")

        except Exception as e:
            LOGGER.warning(f"JioSaavn {api_base} error: {str(e)[:80]}")

    return None, None


# =====================================================
# SOURCE 3: YOUTUBE (Fallback)
# =====================================================

_YT_STRATEGIES = [
    ("bestaudio/best", ["web_creator"], "yt:web_creator"),
    ("bestaudio/best", ["mweb"], "yt:mweb"),
    ("bestaudio/best", ["ios"], "yt:ios"),
    ("bestaudio/best", None, "yt:default"),
]


def _youtube_search_sync(query: str):
    try:
        from youtubesearchpython import VideosSearch
        search = VideosSearch(query, limit=1)
        result = search.result()
        if not result or not result.get("result"):
            return None
        video = result["result"][0]
        vid = video.get("id")
        title = video.get("title", "Unknown")
        dur_text = video.get("duration", "0:00")
        dur_parts = str(dur_text).split(":")
        try:
            if len(dur_parts) == 3:
                duration = int(dur_parts[0]) * 3600 + int(dur_parts[1]) * 60 + int(dur_parts[2])
            elif len(dur_parts) == 2:
                duration = int(dur_parts[0]) * 60 + int(dur_parts[1])
            else:
                duration = 0
        except Exception:
            duration = 0
        thumbs = video.get("thumbnails")
        thumb = thumbs[-1]["url"] if thumbs else f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
        channel = video.get("channel", {}).get("name", "YouTube")
        return {
            "title": title, "duration": duration,
            "link": f"https://www.youtube.com/watch?v={vid}",
            "thumb": thumb, "channel": channel, "id": vid,
            "source": "YouTube",
        }
    except Exception as e:
        LOGGER.error(f"YT search error: {e}")
        return None


def _youtube_download(url: str, video: bool) -> str:
    cleanup_downloads()
    suffix = "_v" if video else ""
    outtmpl = f"downloads/yt_%(id)s{suffix}.%(ext)s"
    all_exts = [".m4a", ".webm", ".opus", ".mp3", ".ogg", ".mp4"]

    for fmt_str, player_client, desc in _YT_STRATEGIES[:3]:
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
                for ext in all_exts:
                    if os.path.exists(base + ext):
                        return base + ext
                if os.path.exists(fname):
                    return fname
        except Exception as e:
            LOGGER.warning(f"YT download [{desc}]: {str(e)[:60]}")
        time.sleep(1)

    return None


# =====================================================
# MASTER SEARCH + GET: multi-source
# =====================================================

def search_and_get_media(query: str, video: bool):
    """
    Multi-source fallback:
      1. SoundCloud  2. JioSaavn  3. YouTube
    Returns (local_file_path, info_dict) or raises.
    """
    errors = []

    LOGGER.info("=== Source 1: SoundCloud ===")
    try:
        path, info = _soundcloud_search_and_get(query, video)
        if path and info:
            return path, info
        errors.append("SoundCloud: no results")
    except Exception as e:
        errors.append(f"SC: {str(e)[:50]}")

    LOGGER.info("=== Source 2: JioSaavn ===")
    try:
        path, info = _jiosaavn_search_and_get(query, video)
        if path and info:
            return path, info
        errors.append("JioSaavn: no results")
    except Exception as e:
        errors.append(f"JS: {str(e)[:50]}")

    LOGGER.info("=== Source 3: YouTube ===")
    try:
        yt_info = _youtube_search_sync(query)
        if yt_info:
            path = _youtube_download(yt_info["link"], video)
            if path:
                return path, yt_info
        errors.append("YouTube: blocked/no results")
    except Exception as e:
        errors.append(f"YT: {str(e)[:50]}")

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
            LOGGER.info(f"Playing in {chat_id}")
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
# QUEUE: auto-play next song when current ends
# =====================================================

@calls.on_stream_end()
async def _on_stream_end(client, update):
    """Auto-play next song from queue when current one ends."""
    chat_id = update.chat_id
    LOGGER.info(f"Stream ended in {chat_id}")

    # Clean up current song's file
    current = ACTIVE_CHATS.pop(chat_id, None)

    # Check queue
    if chat_id not in QUEUES or not QUEUES[chat_id]:
        LOGGER.info(f"Queue empty for {chat_id}, leaving VC")
        try:
            await calls.leave_call(chat_id)
        except Exception:
            pass
        try:
            await app.send_message(
                chat_id,
                "🎵 <b>কিউ শেষ!</b>\nআরো গান শুনতে <code>/play</code> দাও।"
            )
        except Exception:
            pass
        return

    # Get next song from queue
    next_query, next_video, requester = QUEUES[chat_id].popleft()
    LOGGER.info(f"Auto-playing next: '{next_query}' for {chat_id}")

    try:
        status = await app.send_message(
            chat_id,
            f"⏭ <b>পরবর্তী গান লোড হচ্ছে...</b>\n🔎 {next_query}"
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
            # Try next in queue
            asyncio.create_task(_try_next_in_queue(chat_id))
            return

        result = await try_play_stream(chat_id, str(media_path), next_video)

        if result is True:
            ACTIVE_CHATS[chat_id] = info
            source_name = info.get("source", "Unknown")
            icon = "🎬" if next_video else "🎵"
            queue_len = len(QUEUES.get(chat_id, []))

            caption = (
                f"╭───❀ ✦ ❀───╮\n"
                f"  {icon} <b>এখন {'ভিডিও' if next_video else 'গান'} বাজছে</b>\n"
                f"╰───❀ ✦ ❀───╯\n\n"
                f"🎵 <b>শিরোনাম:</b> {info.get('title', '?')}\n"
                f"⏱ <b>সময়:</b> <code>{fmt_dur(info.get('duration'))}</code>\n"
                f"📺 <b>শিল্পী:</b> {info.get('channel', '?')}\n"
                f"📡 <b>সোর্স:</b> {source_name}\n"
                f"🙋 <b>অনুরোধ:</b> {requester}\n"
                f"📋 <b>কিউতে বাকি:</b> {queue_len} টি\n\n"
                f"⏸ <code>/pause</code> ▶️ <code>/resume</code> ⏭ <code>/skip</code> 🛑 <code>/stop</code>"
            )

            if status:
                try:
                    await status.delete()
                except Exception:
                    pass

            thumb = info.get("thumb", "")
            try:
                if thumb and thumb.startswith("http"):
                    await app.send_photo(chat_id, photo=thumb, caption=caption)
                else:
                    await app.send_message(chat_id, caption)
            except Exception:
                await app.send_message(chat_id, caption)
        else:
            if status:
                await status.edit(f"❌ পরবর্তী গান চালানো যায়নি: {result}")
            asyncio.create_task(_try_next_in_queue(chat_id))

    except Exception as e:
        LOGGER.error(f"Auto-play error: {e}")
        if status:
            try:
                await status.edit(f"❌ ত্রুটি: <code>{str(e)[:80]}</code>")
            except Exception:
                pass
        asyncio.create_task(_try_next_in_queue(chat_id))


async def _try_next_in_queue(chat_id):
    """Skip to next song if current fails."""
    await asyncio.sleep(2)
    if chat_id in QUEUES and QUEUES[chat_id]:
        # Simulate stream end to trigger next
        class FakeUpdate:
            def __init__(self, cid):
                self.chat_id = cid
        await _on_stream_end(None, FakeUpdate(chat_id))
    else:
        try:
            await calls.leave_call(chat_id)
        except Exception:
            pass


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

    # Allow YouTube URLs as direct input
    is_yt_url = False
    if query.startswith("http"):
        if re.match(
            r'https?://(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/', query
        ):
            is_yt_url = True
        else:
            return await message.reply_text("<b>শুধু YouTube লিংক বা গানের নাম দাও!</b>")
        try:
            from MusicBangla.plugins.security import is_url_blocked
            if is_url_blocked(query):
                return await message.reply_text("<b>এই URL ব্লক করা হয়েছে।</b>")
        except ImportError:
            pass

    requester = message.from_user.mention
    chat_id = message.chat.id

    # If something is already playing, ADD TO QUEUE
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

    # Nothing playing — play immediately
    status = await message.reply_text(
        "<b>খুঁজছি...</b> (SoundCloud + JioSaavn + YouTube)"
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

        # For YouTube URL, try YouTube first then fallback
        search_query = query
        if is_yt_url:
            await status.edit("<b>YouTube লিংক থেকে লোড হচ্ছে...</b>")
            yt_info = await loop.run_in_executor(None, _youtube_search_sync,
                query.split("?v=")[-1].split("&")[0] if "v=" in query else query)
            if yt_info:
                search_query = yt_info.get("title", query)

        # Search and download
        await status.edit(
            f"📥 <b>ডাউনলোড হচ্ছে...</b>\n"
            f"🔎 <code>{search_query[:50]}</code>"
        )

        try:
            media_path, info = await asyncio.wait_for(
                loop.run_in_executor(None, search_and_get_media, search_query, video),
                timeout=120
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
        icon = "🎬" if video else "🎵"
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

        # Success message
        try:
            await status.delete()
        except Exception:
            pass

        caption = (
            f"╭───❀ ✦ ❀───╮\n"
            f"  {icon} <b>এখন {'ভিডিও' if video else 'গান'} বাজছে</b>\n"
            f"╰───❀ ✦ ❀───╯\n\n"
            f"🎵 <b>শিরোনাম:</b> {info.get('title', '?')}\n"
            f"⏱ <b>সময়:</b> <code>{fmt_dur(info.get('duration'))}</code>\n"
            f"📺 <b>শিল্পী:</b> {info.get('channel', '?')}\n"
            f"📡 <b>সোর্স:</b> {source_name}\n"
            f"🙋 <b>অনুরোধ:</b> {requester}\n\n"
            f"⏸ <code>/pause</code> ▶️ <code>/resume</code> "
            f"⏭ <code>/skip</code> 🛑 <code>/stop</code>\n"
            f"📋 <code>/queue</code>"
        )
        thumb = info.get("thumb", "")
        try:
            if thumb and thumb.startswith("http"):
                await message.reply_photo(photo=thumb, caption=caption)
            else:
                await message.reply_text(caption)
        except Exception:
            await message.reply_text(caption)

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
    """Clear the queue for this chat."""
    chat_id = message.chat.id
    if chat_id in QUEUES:
        count = len(QUEUES[chat_id])
        QUEUES[chat_id].clear()
        await message.reply_text(f"🗑 <b>{count} টি গান কিউ থেকে মুছে ফেলা হয়েছে।</b>")
    else:
        await message.reply_text("<b>কিউ আগে থেকেই খালি!</b>")
