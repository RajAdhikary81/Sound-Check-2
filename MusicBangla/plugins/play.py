import os
import asyncio
import time
import re
import yt_dlp
from pyrogram import filters
from pyrogram.types import Message
from pytgcalls.types import MediaStream
from youtubesearchpython import VideosSearch

import config
from MusicBangla import app, assistant, calls, LOGGER


os.makedirs("downloads", exist_ok=True)
ACTIVE_CHATS = {}

# --- Rate limiting ---
_USER_COOLDOWN = {}
_COOLDOWN_SECONDS = 5

# --- Cookies ---
_COOKIE_FILE = "cookies.txt" if os.path.exists("cookies.txt") else None
if _COOKIE_FILE:
    LOGGER.info("cookies.txt loaded for yt-dlp")


# =====================================================
# FORMAT STRATEGIES — multiple fallback chains
# =====================================================

_AUDIO_STRATEGIES = [
    # Strategy 1: standard best audio
    "bestaudio/best",
    # Strategy 2: specific containers
    "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio[ext=opus]/bestaudio/best",
    # Strategy 3: any audio with decent bitrate
    "worstaudio/worst",
]

_VIDEO_STRATEGIES = [
    # Strategy 1: standard best <=720p
    "best[height<=720]/best",
    # Strategy 2: separate video+audio merge
    "bestvideo[height<=720]+bestaudio/bestvideo+bestaudio/best",
    # Strategy 3: any mp4
    "best[ext=mp4]/best",
    # Strategy 4: absolute fallback
    "worst",
]

# YouTube player client fallbacks — helps bypass restrictions
_PLAYER_CLIENTS = [
    None,  # default
    ["web"],
    ["android"],
    ["ios"],
    ["tv"],
    ["web", "android"],
    ["mweb"],
]


def _make_opts(fmt: str, player_client=None, download: bool = False, outtmpl: str = None):
    """yt-dlp options builder with player client support"""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "format": fmt,
        "noplaylist": True,
        "socket_timeout": 20,
        "retries": 3,
        "fragment_retries": 3,
        "ignoreerrors": False,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "prefer_insecure": True,
        "no_check_formats": True,
        "source_address": "0.0.0.0",
    }
    if player_client:
        opts["extractor_args"] = {"youtube": {"player_client": player_client}}
    if _COOKIE_FILE:
        opts["cookiefile"] = _COOKIE_FILE
    if outtmpl:
        opts["outtmpl"] = outtmpl
    return opts


def cleanup_downloads():
    """Delete old download files to save disk space"""
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
# SEARCH
# =====================================================

def yt_search_sync(query: str):
    """YouTube search via youtube-search-python (sync)"""
    try:
        search = VideosSearch(query, limit=1)
        result = search.result()

        if not result or not result.get("result"):
            LOGGER.warning(f"No results for: {query}")
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

        info = {
            "title": title,
            "duration": duration,
            "link": f"https://www.youtube.com/watch?v={vid}",
            "thumb": thumb,
            "channel": channel,
            "id": vid,
        }
        LOGGER.info(f"Found: {title} | {vid} | {dur_text}")
        return info

    except Exception as e:
        LOGGER.error(f"Search error: {e}")
        return None


# =====================================================
# STREAM URL — multi-strategy retry with 2-3s intervals
# =====================================================

def get_stream_url(url: str, video: bool):
    """
    Try to get a direct stream URL using multiple format strategies
    and player client combinations. Retries every 2-3 seconds.
    """
    strategies = _VIDEO_STRATEGIES if video else _AUDIO_STRATEGIES

    for strat_idx, fmt in enumerate(strategies):
        for pc_idx, player_client in enumerate(_PLAYER_CLIENTS):
            pc_name = str(player_client) if player_client else "default"
            LOGGER.info(
                f"Stream attempt: fmt={fmt[:30]}... client={pc_name}"
            )
            opts = _make_opts(fmt, player_client=player_client)
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)

                    stream_url = info.get("url")
                    if stream_url:
                        LOGGER.info(
                            f"Got stream URL via fmt strategy {strat_idx}, "
                            f"client={pc_name}, format={info.get('format', '?')}"
                        )
                        return stream_url

                    # merged format — extract audio/video URL
                    req_fmts = info.get("requested_formats")
                    if req_fmts:
                        for f in req_fmts:
                            if not video and f.get("acodec") != "none":
                                LOGGER.info(f"Got audio from merged: {f.get('format', '?')}")
                                return f.get("url")
                            if video and f.get("vcodec") != "none":
                                LOGGER.info(f"Got video from merged: {f.get('format', '?')}")
                                return f.get("url")
                        # if video, return first available
                        if video and req_fmts:
                            return req_fmts[0].get("url")

            except Exception as e:
                err_str = str(e)
                LOGGER.warning(f"Stream failed (fmt={strat_idx}, client={pc_name}): {err_str[:80]}")

            # Wait 2-3 seconds before next attempt
            time.sleep(2)

    LOGGER.error(f"All stream strategies exhausted for {url}")
    return None


# =====================================================
# DOWNLOAD MEDIA — multi-strategy retry fallback
# =====================================================

def download_media(url: str, video: bool):
    """Download media with multiple format/client fallback strategies"""
    strategies = _VIDEO_STRATEGIES if video else _AUDIO_STRATEGIES
    suffix = "_v" if video else ""
    outtmpl = f"downloads/%(id)s{suffix}.%(ext)s"

    for strat_idx, fmt in enumerate(strategies):
        for pc_idx, player_client in enumerate(_PLAYER_CLIENTS[:4]):  # limit client retries for download
            pc_name = str(player_client) if player_client else "default"
            LOGGER.info(f"Download attempt: fmt={fmt[:30]}... client={pc_name}")
            opts = _make_opts(fmt, player_client=player_client, download=True, outtmpl=outtmpl)
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    fname = ydl.prepare_filename(info)

                    base = os.path.splitext(fname)[0]
                    all_exts = [".m4a", ".webm", ".opus", ".mp3", ".ogg", ".wav",
                                ".mp4", ".mkv", ".3gp", ".flv"]
                    for ext in all_exts:
                        if os.path.exists(base + ext):
                            LOGGER.info(f"Downloaded: {base + ext}")
                            return base + ext

                    if os.path.exists(fname):
                        LOGGER.info(f"Downloaded: {fname}")
                        return fname

                    # fallback: search by id
                    vid_id = info.get("id", "")
                    if vid_id:
                        prefix = f"downloads/{vid_id}{suffix}"
                        for ext in all_exts:
                            if os.path.exists(prefix + ext):
                                LOGGER.info(f"Downloaded (id match): {prefix + ext}")
                                return prefix + ext

            except Exception as e:
                LOGGER.warning(f"Download failed (fmt={strat_idx}, client={pc_name}): {str(e)[:80]}")

            time.sleep(2)

    raise Exception("All download strategies exhausted. Try a different song.")


def get_media(url: str, video: bool):
    """Try stream URL first, then download as fallback."""
    # Method 1: Direct stream URL (fast, no download)
    stream_url = get_stream_url(url, video)
    if stream_url:
        LOGGER.info("Using direct stream URL (no download needed)")
        return stream_url

    # Method 2: Download fallback
    LOGGER.info("Stream URL failed, falling back to download...")
    cleanup_downloads()
    return download_media(url, video)


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
            chat_id=message.chat.id,
            message_id=message.id,
            emoji=emoji,
        )
    except Exception:
        pass


async def ensure_assistant(chat_id: int):
    """Ensure assistant is in the group"""
    try:
        me = await assistant.get_me()
        await assistant.get_chat_member(chat_id, me.id)
        LOGGER.info(f"Assistant already in {chat_id}")
        return True
    except Exception:
        LOGGER.info(f"Assistant not in {chat_id}, joining...")

    try:
        invite = await app.export_chat_invite_link(chat_id)
        await assistant.join_chat(invite)
        await asyncio.sleep(5)
        LOGGER.info("Assistant joined via invite")
        return True
    except Exception as e:
        LOGGER.warning(f"Invite join failed: {e}")

    try:
        chat = await app.get_chat(chat_id)
        if chat.username:
            await assistant.join_chat(chat.username)
            await asyncio.sleep(5)
            LOGGER.info(f"Assistant joined via @{chat.username}")
            return True
    except Exception as e:
        LOGGER.warning(f"Username join failed: {e}")

    LOGGER.error(f"Could not join {chat_id}")
    return False


async def try_play_stream(chat_id, media_path, video, max_retries=4):
    """Play in voice chat with retry logic — 3s intervals"""
    if video:
        stream = MediaStream(media_path, video_flags=MediaStream.Flags.AUTO_DETECT)
    else:
        stream = MediaStream(media_path, video_flags=MediaStream.Flags.IGNORE)

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            LOGGER.info(f"Play attempt {attempt}/{max_retries}")
            await calls.play(chat_id, stream)
            LOGGER.info(f"Playing in {chat_id}")
            return True
        except Exception as e:
            last_error = e
            err = str(e).lower()
            LOGGER.error(f"Play attempt {attempt} failed: {e}")

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
# SECURITY: Input validation & rate limiting
# =====================================================

def _sanitize_query(text: str) -> str:
    """Sanitize user input to prevent injection"""
    # Remove any suspicious characters, keep only safe ones
    text = text.strip()
    # Limit length
    if len(text) > 200:
        text = text[:200]
    # Remove null bytes and control characters
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text


def _check_rate_limit(user_id: int) -> bool:
    """Returns True if user is rate-limited (should wait)"""
    now = time.time()
    last = _USER_COOLDOWN.get(user_id, 0)
    if now - last < _COOLDOWN_SECONDS:
        return True
    _USER_COOLDOWN[user_id] = now
    return False


def _is_valid_url(text: str) -> bool:
    """Check if text is a valid YouTube URL"""
    yt_patterns = [
        r'https?://(www\.)?youtube\.com/watch\?v=[\w-]+',
        r'https?://youtu\.be/[\w-]+',
        r'https?://music\.youtube\.com/watch\?v=[\w-]+',
    ]
    return any(re.match(p, text) for p in yt_patterns)


# =====================================================
# MAIN PLAY FUNCTION
# =====================================================

async def _play(client, message: Message, video: bool):
    """Main play function with retry, fallback, and security"""
    await safe_react(client, message, config.random_emoji())
    cmd = "vplay" if video else "play"

    # Security: rate limiting
    if _check_rate_limit(message.from_user.id):
        return await message.reply_text(
            f"⏳ **অনুগ্রহ করে {_COOLDOWN_SECONDS} সেকেন্ড অপেক্ষা করুন।**"
        )

    if len(message.command) < 2 and not message.reply_to_message:
        return await message.reply_text(
            f"**গানের নাম দাও!**\n\nউদাহরণ: `/{cmd} tum hi ho`"
        )

    raw_query = (
        " ".join(message.command[1:])
        if len(message.command) > 1
        else (message.reply_to_message.text or "")
    )

    # Security: sanitize input
    query = _sanitize_query(raw_query)
    if not query:
        return await message.reply_text("**সঠিক গানের নাম দাও!**")

    status = await message.reply_text("**খুঁজছি...**")

    try:
        # Step 1: Search
        LOGGER.info(f"Searching: {query}")
        loop = asyncio.get_event_loop()
        try:
            info = await asyncio.wait_for(
                loop.run_in_executor(None, yt_search_sync, query),
                timeout=15,
            )
        except asyncio.TimeoutError:
            return await status.edit("Search timeout. Try again.")
        except Exception as e:
            LOGGER.error(f"Search failed: {e}")
            return await status.edit(f"Search failed: `{str(e)[:80]}`")

        if not info:
            return await status.edit(
                f"**'{query}'** not found.\nTry a different name."
            )

        # Step 2: Status update
        icon = "🎬" if video else "🎵"
        await status.edit(
            f"📥 **মিডিয়া লোড হচ্ছে...**\n\n"
            f"{icon} `{info['title'][:50]}`\n"
            f"⏱ `{fmt_dur(info['duration'])}`\n\n"
            f"⏳ অপেক্ষা করুন (retry সহ লোড হচ্ছে)..."
        )

        # Step 3: Assistant + Media (parallel)
        LOGGER.info(f"Getting media: {info['link']}")

        assistant_ok, media_path = await asyncio.gather(
            ensure_assistant(message.chat.id),
            loop.run_in_executor(None, get_media, info["link"], video),
            return_exceptions=True,
        )

        if isinstance(assistant_ok, Exception) or assistant_ok is False:
            LOGGER.error(f"Assistant error: {assistant_ok}")
            return await status.edit(
                "**Assistant গ্রুপে যোগ হতে পারেনি!**\n\n"
                "Assistant অ্যাকাউন্ট manually গ্রুপে add করুন,\n"
                "বটকে admin করুন, তারপর `/play` দিন।"
            )

        if isinstance(media_path, Exception):
            LOGGER.error(f"Media error: {media_path}")
            return await status.edit(
                f"**ডাউনলোড ব্যর্থ!**\n`{str(media_path)[:100]}`\n\n"
                f"আবার চেষ্টা করুন বা অন্য গান দিন।"
            )

        if not media_path:
            return await status.edit("মিডিয়া পাওয়া যায়নি। অন্য গান দিয়ে চেষ্টা করুন।")

        LOGGER.info(f"Media ready: {media_path}")

        # Step 4: Play with retry
        await status.edit("🎶 **Voice Chat-এ যোগ হচ্ছে...**")
        await asyncio.sleep(1)

        result = await try_play_stream(message.chat.id, str(media_path), video)

        if result is True:
            ACTIVE_CHATS[message.chat.id] = info
        elif result == "NO_VC":
            return await status.edit(
                "**Voice Chat চালু নেই!**\n\n"
                "গ্রুপে Voice Chat শুরু করুন,\n"
                "তারপর `/play` দিন।"
            )
        elif result == "NO_PERM":
            return await status.edit(
                "**Permission নেই!**\n\n"
                "Assistant-কে admin করুন\n"
                "(Manage Voice Chats permission দিন)।"
            )
        else:
            return await status.edit(
                f"**স্ট্রিমিং ব্যর্থ!**\n`{result}`\n\n`/stop` করে আবার `/play` দিন।"
            )

        # Step 5: Success message
        try:
            await status.delete()
        except Exception:
            pass

        caption = (
            f"╭───❀ ✦ ❀───╮\n"
            f"  {icon} **এখন {'ভিডিও' if video else 'গান'} বাজছে**\n"
            f"╰───❀ ✦ ❀───╯\n\n"
            f"🎵 **শিরোনাম:** {info['title']}\n"
            f"⏱ **সময়:** `{fmt_dur(info['duration'])}`\n"
            f"📺 **চ্যানেল:** {info['channel']}\n"
            f"🙋 **অনুরোধকারী:** {message.from_user.mention}\n\n"
            f"▫️ ⏸ `/pause` ▶️ `/resume` ⏭ `/skip` 🛑 `/stop`"
        )
        try:
            await message.reply_photo(photo=info["thumb"], caption=caption)
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
            await status.edit(f"ত্রুটি: `{str(e)[:100]}`")
        except Exception:
            pass


@app.on_message(filters.command(["play", "p"]) & filters.group)
async def play_cmd(client, message: Message):
    await _play(client, message, video=False)


@app.on_message(filters.command(["vplay", "vp"]) & filters.group)
async def vplay_cmd(client, message: Message):
    await _play(client, message, video=True)
