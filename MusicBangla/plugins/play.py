import os
import asyncio
import yt_dlp
from pyrogram import filters
from pyrogram.types import Message
from pytgcalls.types import MediaStream

import config
from MusicBangla import app, assistant, calls, LOGGER


# Fast & lightweight yt-dlp options (YouTube bot-detection bypass সহ)
COMMON_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "geo_bypass": True,
    "nocheckcertificate": True,
    "noplaylist": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "concurrent_fragment_downloads": 5,
    "retries": 5,
    "fragment_retries": 5,
    # YouTube bot-detection bypass (ইউটিউব ব্লকিং এড়ানোর জন্য)
    "extractor_args": {
        "youtube": {
            "player_client": ["tv", "ios", "android_vr", "web"],
            "player_skip": ["webpage", "configs"],
        }
    },
    "http_headers": {
        "User-Agent": "com.google.android.youtube/19.09.37 (Linux; U; Android 14) gzip",
    },
}

# cookies.txt ফাইল থাকলে সেটি ব্যবহারের ব্যবস্থা (ধাপ ২ এর জন্য)
if os.path.exists("cookies.txt"):
    COMMON_OPTS["cookiefile"] = "cookies.txt"

AUDIO_OPTS = {
    **COMMON_OPTS,
    "format": "bestaudio[ext=m4a]/bestaudio/best",
    "outtmpl": "downloads/%(id)s.%(ext)s",
}

VIDEO_OPTS = {
    **COMMON_OPTS,
    "format": "best[height<=480][ext=mp4]/best[height<=480]/best",
    "outtmpl": "downloads/%(id)s_v.%(ext)s",
}

os.makedirs("downloads", exist_ok=True)
ACTIVE_CHATS = {}  # chat_id -> info


def yt_search(query: str):
    """yt-dlp দিয়েই search — কোনো external API/proxy লাগে না।"""
    opts = {
        **COMMON_OPTS,
        "skip_download": True,
        "extract_flat": "in_playlist",
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        data = ydl.extract_info(f"ytsearch1:{query}", download=False)
        if not data or not data.get("entries"):
            return None
        e = data["entries"][0]
        vid = e.get("id")
        return {
            "title": e.get("title", "Unknown"),
            "duration": e.get("duration") or 0,
            "link": f"https://www.youtube.com/watch?v={vid}",
            "thumb": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
            "channel": e.get("channel") or e.get("uploader") or "YouTube",
            "id": vid,
        }


def download_media(url: str, video: bool):
    opts = VIDEO_OPTS if video else AUDIO_OPTS
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


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
        await client.send_reaction(chat_id=message.chat.id, message_id=message.id, emoji=emoji)
    except Exception:
        pass


async def ensure_assistant(chat_id: int, status):
    try:
        await assistant.get_chat(chat_id)
        return True
    except Exception:
        try:
            invite = await app.export_chat_invite_link(chat_id)
            await assistant.join_chat(invite)
            await asyncio.sleep(2)
            return True
        except Exception as e:
            LOGGER.warning(f"Assistant join failed: {e}")
            await status.edit(
                "❌ Assistant অ্যাকাউন্ট গ্রুপে যোগ হতে পারেনি।\n\n"
                "🔧 Assistant অ্যাকাউন্টটি manually গ্রুপে add করুন, তারপর আবার চেষ্টা করুন।"
            )
            return False


async def _play(client, message: Message, video: bool):
    await safe_react(client, message, config.random_emoji())

    cmd_name = "vplay" if video else "play"
    if len(message.command) < 2 and not message.reply_to_message:
        return await message.reply_text(
            f"❌ <b>{'ভিডিও' if video else 'গানের'} নাম দাও!</b>\n\n"
            f"উদাহরণ: <code>/{cmd_name} tum hi ho</code>"
        )

    query = (
        " ".join(message.command[1:])
        if len(message.command) > 1
        else (message.reply_to_message.text or "")
    )
    status = await message.reply_text("🔎 <b>খুঁজছি...</b>")

    loop = asyncio.get_event_loop()

    # Step 1: search (fast)
    try:
        info = await loop.run_in_executor(None, yt_search, query)
    except Exception as e:
        LOGGER.error(f"Search error: {e}")
        return await status.edit(f"❌ Search এ সমস্যা: <code>{e}</code>")

    if not info:
        return await status.edit("❌ কোনো ফলাফল পাওয়া যায়নি। অন্য নাম দিন।")

    icon = "🎬" if video else "🎵"
    await status.edit(
        f"📥 <b>ডাউনলোড হচ্ছে...</b>\n\n"
        f"{icon} <code>{info['title']}</code>\n"
        f"⏱ <code>{fmt_dur(info['duration'])}</code>"
    )

    # Step 2 & 3: Assistant join + download (parallel = faster)
    assistant_task = ensure_assistant(message.chat.id, status)
    download_task = loop.run_in_executor(None, download_media, info["link"], video)

    assistant_ok = await assistant_task
    if not assistant_ok:
        return

    try:
        media_path = await download_task
    except Exception as e:
        LOGGER.error(f"Download error: {e}")
        return await status.edit(f"❌ ডাউনলোডে সমস্যা: <code>{e}</code>")

    # Step 4: Stream in VC
    try:
        if video:
            stream = MediaStream(media_path, video_flags=MediaStream.Flags.AUTO_DETECT)
        else:
            stream = MediaStream(media_path, video_flags=MediaStream.Flags.IGNORE)
        await calls.play(message.chat.id, stream)
        ACTIVE_CHATS[message.chat.id] = info
    except Exception as e:
        LOGGER.error(f"Play error: {e}")
        return await status.edit(
            f"❌ চালানো গেল না।\n\n<b>Error:</b> <code>{e}</code>\n\n"
            "নিশ্চিত করুন:\n• Voice Chat চালু আছে\n• বট admin (Manage VC permission)\n• Assistant গ্রুপে আছে"
        )

    await status.delete()
    caption = (
        f"╭───❀ ✦ ❀───╮\n"
        f"   {icon} <b>এখন {'ভিডিও' if video else ''} বাজছে</b>\n"
        f"╰───❀ ✦ ❀───╯\n\n"
        f"🎵 <b>শিরোনাম:</b> {info['title']}\n"
        f"⏱ <b>সময়:</b> <code>{fmt_dur(info['duration'])}</code>\n"
        f"📺 <b>চ্যানেল:</b> {info['channel']}\n"
        f"🙋 <b>অনুরোধকারী:</b> {message.from_user.mention}\n\n"
        f"▫️ ⏸ /pause  ▶️ /resume  ⏭ /skip  🛑 /stop"
    )
    try:
        await message.reply_photo(photo=info["thumb"], caption=caption)
    except Exception:
        await message.reply_text(caption)

    # Sticker (non-blocking)
    try:
        await asyncio.sleep(0.3)
        await message.reply_sticker(config.random_play_sticker())
    except Exception:
        pass


@app.on_message(filters.command(["play", "p"]) & filters.group)
async def play_cmd(client, message: Message):
    await _play(client, message, video=False)


@app.on_message(filters.command(["vplay", "vp"]) & filters.group)
async def vplay_cmd(client, message: Message):
    await _play(client, message, video=True)
    
