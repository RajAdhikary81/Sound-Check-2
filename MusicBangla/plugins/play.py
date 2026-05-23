import os
import asyncio
import yt_dlp
from pyrogram import filters
from pyrogram.types import Message
from pytgcalls.types import MediaStream

import config
from MusicBangla import app, assistant, calls, LOGGER


# ⚡ আল্ট্রা-ফাস্ট yt-dlp অপশন্স (বড় ফাইল দ্রুত ডাউনলোড করবে)
COMMON_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "geo_bypass": True,
    "nocheckcertificate": True,
    "noplaylist": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "concurrent_fragment_downloads": 10,  # ৩ থেকে ১০ করা হয়েছে (দ্রুত ডাউনলোড)
    "retries": 5,
    "fragment_retries": 5,
    "socket_timeout": 30,
    "extractor_args": {
        "youtube": {
            "player_client": ["tv", "ios", "android_vr", "web", "mweb"],
            "player_skip": ["webpage", "configs", "js"],
        }
    },
    "http_headers": {
        "User-Agent": "com.google.android.youtube/19.09.37 (Linux; U; Android 14) gzip",
    },
}

# cookies.txt ফাইল থাকলে ব্যবহার করবে
if os.path.exists("cookies.txt"):
    COMMON_OPTS["cookiefile"] = "cookies.txt"

# 🎵 অডিও (সবচেয়ে ভাল কোয়ালিটি, দ্রুত)
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

# 🎬 ভিডিও (480p বা তার নিচে - দ্রুত স্ট্রিম করার জন্য)
VIDEO_OPTS = {
    **COMMON_OPTS,
    "format": "best[height<=480][ext=mp4]/best[height<=480]/bestvideo[height<=480]+bestaudio/best",
    "outtmpl": "downloads/%(id)s_v.%(ext)s",
}

os.makedirs("downloads", exist_ok=True)
ACTIVE_CHATS = {}  # chat_id -> গানের ইনফো


def yt_search(query: str):
    """✅ ইউটিউব সার্চ করে (এক্সটারনাল API লাগে না)"""
    try:
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
    except Exception as e:
        LOGGER.error(f"Search error: {e}")
        return None


def download_media(url: str, video: bool):
    """✅ মিডিয়া ডাউনলোড ক���ে (দ্রুত)"""
    try:
        opts = VIDEO_OPTS if video else AUDIO_OPTS
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        LOGGER.error(f"Download error: {e}")
        raise Exception(f"ডাউনলোড ব্যর্থ: {str(e)[:100]}")


def fmt_dur(s):
    """মিনিট:সেকেন্ড ফরম্যাটে রূপান্তর করে"""
    if not s:
        return "Live"
    try:
        s = int(s)
        return f"{s // 60}:{s % 60:02d}"
    except Exception:
        return str(s)


async def safe_react(client, message, emoji):
    """নিরাপদভাবে রিঅ্যাকশন পাঠায়"""
    try:
        await client.send_reaction(chat_id=message.chat.id, message_id=message.id, emoji=emoji)
    except Exception:
        pass


async def ensure_assistant(chat_id: int, status_msg):
    """✅ নিশ্চিত করে Assistant গ্রুপে আছে"""
    try:
        # প্রথমে চেক করো Assistant আছে কিনা
        await assistant.get_chat(chat_id)
        LOGGER.info(f"✅ Assistant already in {chat_id}")
        return True
    except Exception as e:
        LOGGER.warning(f"Assistant not in group {chat_id}, trying to join: {e}")
        
        try:
            # ইনভাইট লিংক পান এবং Assistant কে যোগ করুন
            invite = await app.export_chat_invite_link(chat_id)
            LOGGER.info(f"📨 Joining with invite: {invite}")
            await assistant.join_chat(invite)
            await asyncio.sleep(3)  # ৩ সেকেন্ড অপেক্ষা করুন
            LOGGER.info(f"✅ Assistant joined {chat_id}")
            return True
        except Exception as e2:
            error_msg = f"❌ Assistant গ্রুপে যোগ হতে পারেনি: {str(e2)[:80]}\n\n🔧 সমাধান:\n1️⃣ Assistant অ্যাকাউন্টকে manually গ্রুপে add করুন\n2️⃣ বটকে admin করুন\n3️⃣ আবার /play করুন"
            LOGGER.error(error_msg)
            await status_msg.edit(error_msg)
            return False


async def _play(client, message: Message, video: bool):
    """🎵 গান/ভিডিও প্লে করার মূল ফাংশন"""
    await safe_react(client, message, config.random_emoji())

    cmd_name = "vplay" if video else "play"
    
    # কমান্ড চেক করুন
    if len(message.command) < 2 and not message.reply_to_message:
        return await message.reply_text(
            f"❌ <b>গানের নাম দাও!</b>\n\n"
            f"উদাহরণ: <code>/{cmd_name} tum hi ho</code>"
        )

    # গানের নাম পান
    query = (
        " ".join(message.command[1:])
        if len(message.command) > 1
        else (message.reply_to_message.text or "")
    )
    
    status = await message.reply_text("🔎 <b>খুঁজছি...</b>")

    try:
        loop = asyncio.get_event_loop()

        # ✅ Step 1: সার্চ করুন (দ্রুত, ১-২ সেকেন্ড)
        LOGGER.info(f"🔍 Searching: {query}")
        try:
            info = await asyncio.wait_for(
                loop.run_in_executor(None, yt_search, query),
                timeout=10  # ১০ সেকেন্ড টাইমআউট
            )
        except asyncio.TimeoutError:
            return await status.edit("⏱ সার্চ টাইমআউট হয়েছে। ইন্টারনেট চেক করুন।")
        except Exception as e:
            LOGGER.error(f"Search error: {e}")
            return await status.edit(f"❌ সার্চ ব্যর্থ: <code>{str(e)[:80]}</code>")

        if not info:
            return await status.edit(f"❌ '{query}' খুঁজে পাওয়া যায়নি। অন্য নাম দিন।")

        # ✅ Step 2: Status আপডেট করুন
        icon = "🎬" if video else "🎵"
        await status.edit(
            f"📥 <b>ডাউনলোড হচ্ছে...</b>\n\n"
            f"{icon} <code>{info['title'][:50]}</code>...\n"
            f"⏱ <code>{fmt_dur(info['duration'])}</code>\n\n"
            f"⏳ অপেক্ষা করুন..."
        )

        # ✅ Step 3: Assistant নিশ্চিত করুন + ডাউনলোড করুন (সমান্তরাল)
        LOGGER.info(f"🔗 Ensuring assistant in {message.chat.id}")
        assistant_task = ensure_assistant(message.chat.id, status)
        
        LOGGER.info(f"💾 Downloading: {info['link']}")
        download_task = loop.run_in_executor(None, download_media, info["link"], video)

        # দুটোই একসাথে করুন
        assistant_ok, media_path = await asyncio.gather(
            assistant_task,
            download_task,
            return_exceptions=True
        )

        # এরর চেক করুন
        if isinstance(assistant_ok, Exception):
            LOGGER.error(f"Assistant error: {assistant_ok}")
            return await status.edit("❌ Assistant সংযোগ ব্যর্থ")
        
        if isinstance(media_path, Exception):
            LOGGER.error(f"Download error: {media_path}")
            return await status.edit(f"❌ ডাউনলোড ব্যর্থ: {str(media_path)[:80]}")

        if not assistant_ok:
            return  # status ইতিমধ্যে আপডেট হয়েছে

        if not media_path:
            return await status.edit("❌ মিডিয়া ফাইল পাওয়া যায়নি")

        # ✅ Step 4: ভয়েস চ্যাটে স্ট্রিম করুন
        LOGGER.info(f"🎚 Streaming to {message.chat.id}: {media_path}")
        try:
            if video:
                stream = MediaStream(media_path, video_flags=MediaStream.Flags.AUTO_DETECT)
            else:
                stream = MediaStream(media_path, video_flags=MediaStream.Flags.IGNORE)
            
            await calls.play(message.chat.id, stream)
            ACTIVE_CHATS[message.chat.id] = info
            LOGGER.info(f"✅ Playing in {message.chat.id}")
        except Exception as e:
            LOGGER.error(f"Play error: {e}")
            return await status.edit(
                f"❌ স্ট্রিমিং ব্যর্থ।\n\n<b>সমাধান:</b>\n"
                f"✓ Voice Chat চালু আছে কিনা চেক করুন\n"
                f"✓ বটকে admin করুন (Manage VC permission)\n"
                f"✓ Assistant গ্রুপে আছে কিনা চেক করুন\n"
                f"✓ /stop করে আবার /play করুন"
            )

        # ✅ Step 5: সাফল্যের মেসেজ পাঠান
        await status.delete()
        caption = (
            f"╭───❀ ✦ ❀───╮\n"
            f"   {icon} <b>এখন {'ভিডিও' if video else 'গান'} বাজছে</b>\n"
            f"╰───❀ ✦ ❀───╯\n\n"
            f"🎵 <b>শিরোনাম:</b> {info['title']}\n"
            f"⏱ <b>সময়:</b> <code>{fmt_dur(info['duration'])}</code>\n"
            f"📺 <b>চ্যানেল:</b> {info['channel']}\n"
            f"🙋 <b>অনুরোধকারী:</b> {message.from_user.mention}\n\n"
            f"▫️ ⏸ <code>/pause</code>  ▶️ <code>/resume</code>  ⏭ <code>/skip</code>  🛑 <code>/stop</code>"
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

    except Exception as e:
        LOGGER.error(f"Play function error: {e}")
        await status.edit(f"❌ অপ্রত্যাশিত ত্রুটি: {str(e)[:100]}")


@app.on_message(filters.command(["play", "p"]) & filters.group)
async def play_cmd(client, message: Message):
    """🎵 অডিও প্লে করুন"""
    await _play(client, message, video=False)


@app.on_message(filters.command(["vplay", "vp"]) & filters.group)
async def vplay_cmd(client, message: Message):
    """🎬 ভিডিও প্লে করুন"""
    await _play(client, message, video=True)
