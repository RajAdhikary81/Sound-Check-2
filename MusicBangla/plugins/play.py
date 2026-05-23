import os
import asyncio
import yt_dlp
from pyrogram import filters
from pyrogram.types import Message
from pytgcalls.types import MediaStream
from youtubesearchpython import VideosSearch

import config
from MusicBangla import app, assistant, calls, LOGGER

# yt-dlp অপশন্স (শুধু ডাউনলোডের জন্য, সার্চ নয়)
COMMON_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "geo_bypass": True,
    "nocheckcertificate": True,
    "noplaylist": True,
    "source_address": "0.0.0.0",
    "concurrent_fragment_downloads": 10,
    "retries": 5,
    "fragment_retries": 5,
    "socket_timeout": 30,
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    },
}

if os.path.exists("cookies.txt"):
    COMMON_OPTS["cookiefile"] = "cookies.txt"

AUDIO_OPTS = {
    **COMMON_OPTS,
    "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
    "outtmpl": "downloads/%(id)s.%(ext)s",
    "postprocessors": [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "m4a",
            "preferredquality": "192",
        }
    ],
}

VIDEO_OPTS = {
    **COMMON_OPTS,
    "format": "best[height<=480][ext=mp4]/best[height<=480]/bestvideo[height<=480]+bestaudio/best",
    "outtmpl": "downloads/%(id)s_v.%(ext)s",
}

os.makedirs("downloads", exist_ok=True)
ACTIVE_CHATS = {}


def yt_search_sync(query: str):
    """youtube-search-python দিয়ে সার্চ (sync — Heroku-friendly)"""
    try:
        search = VideosSearch(query, limit=1)
        result = search.result()

        if not result or not result.get("result"):
            LOGGER.warning(f"No results for: {query}")
            return None

        video = result["result"][0]
        vid = video.get("id")
        title = video.get("title", "Unknown")

        # duration parse
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

        # thumbnail
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
        LOGGER.info(f"✅ Found: {title} | {vid} | {dur_text}")
        return info

    except Exception as e:
        LOGGER.error(f"Search error: {e}")
        return None


def download_media(url: str, video: bool):
    """মিডিয়া ডাউনলোড করে"""
    try:
        opts = VIDEO_OPTS if video else AUDIO_OPTS
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            fname = ydl.prepare_filename(info)

            # audio post-process হলে extension বদলে যায়
            if not video:
                base = os.path.splitext(fname)[0]
                for ext in [".m4a", ".webm", ".opus", ".mp3", ".ogg"]:
                    if os.path.exists(base + ext):
                        return base + ext
            return fname
    except Exception as e:
        LOGGER.error(f"Download error: {e}")
        raise Exception(f"ডাউনলোড ব্যর্থ: {str(e)[:100]}")


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
    """Assistant গ্রুপে আছে কিনা নিশ্চিত করে"""
    try:
        me = await assistant.get_me()
        await assistant.get_chat_member(chat_id, me.id)
        LOGGER.info(f"✅ Assistant already in {chat_id}")
        return True
    except Exception:
        LOGGER.info(f"⚠️ Assistant not in {chat_id}, joining...")

    # চেষ্টা ১: invite link
    try:
        invite = await app.export_chat_invite_link(chat_id)
        await assistant.join_chat(invite)
        await asyncio.sleep(5)
        LOGGER.info(f"✅ Assistant joined via invite")
        return True
    except Exception as e:
        LOGGER.warning(f"Invite join failed: {e}")

    # চেষ্টা ২: username
    try:
        chat = await app.get_chat(chat_id)
        if chat.username:
            await assistant.join_chat(chat.username)
            await asyncio.sleep(5)
            LOGGER.info(f"✅ Assistant joined via @{chat.username}")
            return True
    except Exception as e:
        LOGGER.warning(f"Username join failed: {e}")

    LOGGER.error(f"❌ Could not join {chat_id}")
    return False


async def try_play_stream(chat_id, media_path, video, max_retries=3):
    """Voice Chat-এ play করে — retry সহ"""
    if video:
        stream = MediaStream(media_path, video_flags=MediaStream.Flags.AUTO_DETECT)
    else:
        stream = MediaStream(media_path, video_flags=MediaStream.Flags.IGNORE)

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            LOGGER.info(f"🎚 Play attempt {attempt}/{max_retries}")
            await calls.play(chat_id, stream)
            LOGGER.info(f"✅ Playing in {chat_id}")
            return True
        except Exception as e:
            last_error = e
            err = str(e).lower()
            LOGGER.error(f"Play attempt {attempt} failed: {e}")

            if "no active group call" in err or "group_call_invalid" in err:
                if attempt < max_retries:
                    await asyncio.sleep(5)
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


async def _play(client, message: Message, video: bool):
    """গান/ভিডিও প্লে করার মূল ফাংশন"""
    await safe_react(client, message, config.random_emoji())
    cmd = "vplay" if video else "play"

    if len(message.command) < 2 and not message.reply_to_message:
        return await message.reply_text(
            f"❌ **গানের নাম দাও!**\n\nউদাহরণ: `/{cmd} tum hi ho`"
        )

    query = (
        " ".join(message.command[1:])
        if len(message.command) > 1
        else (message.reply_to_message.text or "")
    )

    status = await message.reply_text("🔎 **খুঁজছি...**")

    try:
        # Step 1: সার্চ (youtube-search-python — async)
        LOGGER.info(f"🔍 Searching: {query}")
        loop = asyncio.get_event_loop()
        try:
            info = await asyncio.wait_for(
                loop.run_in_executor(None, yt_search_sync, query),
                timeout=15,
            )
        except asyncio.TimeoutError:
            return await status.edit("⏱ সার্চ টাইমআউট। আবার চেষ্টা করুন।")
        except Exception as e:
            LOGGER.error(f"Search failed: {e}")
            return await status.edit(f"❌ সার্চ ব্যর্থ: `{str(e)[:80]}`")

        if not info:
            return await status.edit(
                f"❌ **'{query}'** খুঁজে পাওয়া যায়নি।\n"
                f"অন্য নাম দিয়ে চেষ্টা করুন।"
            )

        # Step 2: Status
        icon = "🎬" if video else "🎵"
        await status.edit(
            f"📥 **ডাউনলোড হচ্ছে...**\n\n"
            f"{icon} `{info['title'][:50]}`\n"
            f"⏱ `{fmt_dur(info['duration'])}`\n\n"
            f"⏳ অপেক্ষা করুন..."
        )

        # Step 3: Assistant + Download (parallel)
        LOGGER.info(f"💾 Downloading: {info['link']}")

        assistant_ok, media_path = await asyncio.gather(
            ensure_assistant(message.chat.id),
            loop.run_in_executor(None, download_media, info["link"], video),
            return_exceptions=True,
        )

        if isinstance(assistant_ok, Exception) or assistant_ok is False:
            LOGGER.error(f"Assistant error: {assistant_ok}")
            return await status.edit(
                "❌ **Assistant গ্রুপে যোগ হতে পারেনি!**\n\n"
                "🔧 Assistant অ্যাকাউন্ট manually গ্রুপে add করুন,\n"
                "বটকে admin করুন, তারপর `/play` দিন।"
            )

        if isinstance(media_path, Exception):
            LOGGER.error(f"Download error: {media_path}")
            return await status.edit(
                f"❌ **ডাউনলোড ব্যর্থ!**\n`{str(media_path)[:100]}`\n\nআবার চেষ্টা করুন।"
            )

        if not media_path or not os.path.exists(str(media_path)):
            return await status.edit("❌ মিডিয়া ফাইল পাওয়া যায়নি।")

        LOGGER.info(f"✅ Downloaded: {media_path}")

        # Step 4: Play
        await status.edit("🎶 **Voice Chat-এ যোগ হচ্ছে...**")
        await asyncio.sleep(2)

        result = await try_play_stream(message.chat.id, str(media_path), video)

        if result is True:
            ACTIVE_CHATS[message.chat.id] = info
        elif result == "NO_VC":
            return await status.edit(
                "❌ **Voice Chat চালু নেই!**\n\n"
                "🔧 গ্রুপে Voice Chat শুরু করুন,\n"
                "তারপর `/play` দিন।"
            )
        elif result == "NO_PERM":
            return await status.edit(
                "❌ **Permission নেই!**\n\n"
                "🔧 Assistant-কে admin করুন\n"
                "(Manage Voice Chats permission দিন)।"
            )
        else:
            return await status.edit(
                f"❌ **স্ট্রিমিং ব্যর্থ!**\n`{result}`\n\n`/stop` করে আবার `/play` দিন।"
            )

        # Step 5: সাফল্য
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
            await status.edit(f"❌ ত্রুটি: `{str(e)[:100]}`")
        except Exception:
            pass


@app.on_message(filters.command(["play", "p"]) & filters.group)
async def play_cmd(client, message: Message):
    await _play(client, message, video=False)


@app.on_message(filters.command(["vplay", "vp"]) & filters.group)
async def vplay_cmd(client, message: Message):
    await _play(client, message, video=True)
