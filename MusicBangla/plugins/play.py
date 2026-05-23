import os
import asyncio
import yt_dlp
from pyrogram import filters
from pyrogram.types import Message
from pytgcalls.types import MediaStream

import config
from MusicBangla import app, assistant, calls, LOGGER

# yt-dlp অপশন্স
COMMON_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "geo_bypass": True,
    "nocheckcertificate": True,
    "noplaylist": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "concurrent_fragment_downloads": 10,
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


def yt_search(query: str):
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
    try:
        opts = VIDEO_OPTS if video else AUDIO_OPTS
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
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
            emoji=emoji
        )
    except Exception:
        pass


async def ensure_assistant(chat_id: int):
    """নিশ্চিত করে Assistant গ্রুপে আছে — True/False রিটার্ন করে"""
    # চেক: assistant আছে কিনা
    try:
        me = await assistant.get_me()
        await assistant.get_chat_member(chat_id, me.id)
        LOGGER.info(f"✅ Assistant already in chat {chat_id}")
        return True
    except Exception:
        LOGGER.info(f"⚠️ Assistant not in chat {chat_id}, joining...")

    # চেষ্টা ১: invite link
    try:
        invite = await app.export_chat_invite_link(chat_id)
        await assistant.join_chat(invite)
        await asyncio.sleep(5)
        LOGGER.info(f"✅ Assistant joined via invite link")
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

    LOGGER.error(f"❌ Could not add assistant to {chat_id}")
    return False


async def try_play_stream(chat_id, media_path, video, max_retries=3):
    """Voice Chat-এ stream করার চেষ্টা করে — retry সহ"""
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
            LOGGER.info(f"🎚 Play attempt {attempt}/{max_retries} for chat {chat_id}")
            await calls.play(chat_id, stream)
            LOGGER.info(f"✅ Successfully playing in {chat_id}")
            return True
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            LOGGER.error(f"Play attempt {attempt} failed: {e}")

            if "no active group call" in error_str or "group_call_invalid" in error_str:
                if attempt < max_retries:
                    LOGGER.info(f"⏳ Waiting 5s before retry...")
                    await asyncio.sleep(5)
                    continue
                else:
                    return "NO_VOICE_CHAT"

            elif "not found" in error_str or "chat_admin_required" in error_str:
                return "NO_PERMISSION"

            else:
                if attempt < max_retries:
                    await asyncio.sleep(3)
                    continue
                return f"OTHER_ERROR: {str(e)[:100]}"

    return f"FAILED: {str(last_error)[:100]}"


async def _play(client, message: Message, video: bool):
    """গান/ভিডিও প্লে করার মূল ফাংশন"""
    await safe_react(client, message, config.random_emoji())

    cmd_name = "vplay" if video else "play"

    if len(message.command) < 2 and not message.reply_to_message:
        return await message.reply_text(
            f"❌ **গানের নাম দাও!**\n\n"
            f"উদাহরণ: `/{cmd_name} tum hi ho`"
        )

    query = (
        " ".join(message.command[1:])
        if len(message.command) > 1
        else (message.reply_to_message.text or "")
    )

    status = await message.reply_text("🔎 **খুঁজছি...**")

    try:
        loop = asyncio.get_event_loop()

        # Step 1: সার্চ
        LOGGER.info(f"🔍 Searching: {query}")
        try:
            info = await asyncio.wait_for(
                loop.run_in_executor(None, yt_search, query),
                timeout=15
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

        LOGGER.info(f"✅ Found: {info['title']} ({info['link']})")

        # Step 2: Status আপডেট
        icon = "🎬" if video else "🎵"
        await status.edit(
            f"📥 **ডাউনলোড হচ্ছে...**\n\n"
            f"{icon} `{info['title'][:50]}`...\n"
            f"⏱ `{fmt_dur(info['duration'])}`\n\n"
            f"⏳ অপেক্ষা করুন..."
        )

        # Step 3: Assistant join + Download (সমান্তরাল)
        LOGGER.info(f"🔗 Ensuring assistant in chat {message.chat.id}")
        LOGGER.info(f"💾 Downloading: {info['link']}")

        assistant_ok, media_path = await asyncio.gather(
            ensure_assistant(message.chat.id),
            loop.run_in_executor(None, download_media, info["link"], video),
            return_exceptions=True
        )

        # Assistant error চেক
        if isinstance(assistant_ok, Exception):
            LOGGER.error(f"Assistant error: {assistant_ok}")
            return await status.edit(
                "❌ **Assistant সংযোগ ব্যর্থ!**\n\n"
                "🔧 **সমাধান:**\n"
                "1️⃣ Assistant অ্যাকাউন্ট manually গ্রুপে add করুন\n"
                "2️⃣ বটকে admin করুন\n"
                "3️⃣ আবার `/play` দিন"
            )

        if assistant_ok is False:
            return await status.edit(
                "❌ **Assistant গ্রুপে যোগ হতে পারেনি!**\n\n"
                "🔧 **সমাধান:**\n"
                "1️⃣ Assistant অ্যাকাউন্ট manually গ্রুপে add করুন\n"
                "2️⃣ বটকে admin করুন (Invite Users)\n"
                "3️⃣ আবার `/play` দিন"
            )

        # Download error চেক
        if isinstance(media_path, Exception):
            LOGGER.error(f"Download error: {media_path}")
            return await status.edit(
                f"❌ **ডাউনলোড ব্যর্থ!**\n\n"
                f"`{str(media_path)[:100]}`\n\n"
                f"আবার চেষ্টা করুন।"
            )

        if not media_path or not os.path.exists(str(media_path)):
            # m4a extension fix
            if media_path and not os.path.exists(str(media_path)):
                base = os.path.splitext(str(media_path))[0]
                for ext in [".m4a", ".webm", ".mp3", ".mp4", ".opus"]:
                    if os.path.exists(base + ext):
                        media_path = base + ext
                        break

            if not media_path or not os.path.exists(str(media_path)):
                return await status.edit("❌ মিডিয়া ফাইল পাওয়া যায়নি।")

        LOGGER.info(f"✅ Downloaded: {media_path}")

        # Step 4: Play
        await status.edit(f"🎶 **Voice Chat-এ যোগ হচ্ছে...**")
        await asyncio.sleep(2)  # assistant sync হওয়ার জন্য অপেক্ষা

        result = await try_play_stream(message.chat.id, str(media_path), video)

        if result is True:
            ACTIVE_CHATS[message.chat.id] = info
        elif result == "NO_VOICE_CHAT":
            return await status.edit(
                "❌ **Voice Chat চালু নেই!**\n\n"
                "🔧 **সমাধান:**\n"
                "1️⃣ গ্রুপের নামে ক্লিক করুন\n"
                "2️⃣ ⋮ মেনু → **Voice Chat** শুরু করুন\n"
                "3️⃣ Voice Chat চালু থাকা অবস্থায় `/play` দিন\n\n"
                "⚠️ Voice Chat আপনাকে নিজে শুরু করতে হবে!"
            )
        elif result == "NO_PERMISSION":
            return await status.edit(
                "❌ **Permission নেই!**\n\n"
                "🔧 **সমাধান:**\n"
                "1️⃣ Assistant-কে গ্রুপে **admin** করুন\n"
                "2️⃣ **Manage Voice Chats** permission দিন\n"
                "3️⃣ আবার `/play` দিন"
            )
        else:
            return await status.edit(
                f"❌ **স্ট্রিমিং ব্যর্থ!**\n\n"
                f"`{result}`\n\n"
                "🔧 `/stop` করে আবার `/play` দিন।"
            )

        # Step 5: সাফল্যের মেসেজ
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

        # cleanup: ডাউনলোড ফাইল মুছে ফেলো (RAM বাঁচাতে)
        try:
            if os.path.exists(str(media_path)):
                await asyncio.sleep(30)
                os.remove(str(media_path))
        except Exception:
            pass

    except Exception as e:
        LOGGER.error(f"Play function error: {e}")
        import traceback
        traceback.print_exc()
        try:
            await status.edit(f"❌ অপ্রত্যাশিত ত্রুটি: `{str(e)[:100]}`")
        except Exception:
            pass


@app.on_message(filters.command(["play", "p"]) & filters.group)
async def play_cmd(client, message: Message):
    await _play(client, message, video=False)


@app.on_message(filters.command(["vplay", "vp"]) & filters.group)
async def vplay_cmd(client, message: Message):
    await _play(client, message, video=True)
