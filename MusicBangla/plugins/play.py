import os
import asyncio
import yt_dlp
from pyrogram import filters
from pyrogram.types import Message
from pytgcalls.types import MediaStream

import config
from MusicBangla import app, assistant, calls, LOGGER

# âš¡ à¦†à¦²à§à¦Ÿà§à¦°à¦¾-à¦«à¦¾à¦¸à§à¦Ÿ yt-dlp à¦…à¦ªà¦¶à¦¨à§à¦¸
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

# cookies.txt à¦«à¦¾à¦‡à¦² à¦¥à¦¾à¦•à¦²à§‡ à¦¬à§à¦¯à¦¬à¦¹à¦¾à¦° à¦•à¦°à¦¬à§‡
if os.path.exists("cookies.txt"):
    COMMON_OPTS["cookiefile"] = "cookies.txt"

# ðŸŽµ à¦…à¦¡à¦¿à¦“
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

# ðŸŽ¬ à¦­à¦¿à¦¡à¦¿à¦“
VIDEO_OPTS = {
    **COMMON_OPTS,
    "format": "best[height<=480][ext=mp4]/best[height<=480]/bestvideo[height<=480]+bestaudio/best",
    "outtmpl": "downloads/%(id)s_v.%(ext)s",
}

os.makedirs("downloads", exist_ok=True)
ACTIVE_CHATS = {}  # chat_id -> à¦—à¦¾à¦¨à§‡à¦° à¦‡à¦¨à¦«à§‹


def yt_search(query: str):
    """à¦‡à¦‰à¦Ÿà¦¿à¦‰à¦¬ à¦¸à¦¾à¦°à§à¦š à¦•à¦°à§‡"""
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
    """à¦®à¦¿à¦¡à¦¿à¦¯à¦¼à¦¾ à¦¡à¦¾à¦‰à¦¨à¦²à§‹à¦¡ à¦•à¦°à§‡"""
    try:
        opts = VIDEO_OPTS if video else AUDIO_OPTS
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        LOGGER.error(f"Download error: {e}")
        raise Exception(f"à¦¡à¦¾à¦‰à¦¨à¦²à§‹à¦¡ à¦¬à§à¦¯à¦°à§à¦¥: {str(e)[:100]}")


def fmt_dur(s):
    """à¦®à¦¿à¦¨à¦¿à¦Ÿ:à¦¸à§‡à¦•à§‡à¦¨à§à¦¡ à¦«à¦°à¦®à§à¦¯à¦¾à¦Ÿà§‡ à¦°à§‚à¦ªà¦¾à¦¨à§à¦¤à¦° à¦•à¦°à§‡"""
    if not s:
        return "Live"
    try:
        s = int(s)
        return f"{s // 60}:{s % 60:02d}"
    except Exception:
        return str(s)


async def safe_react(client, message, emoji):
    """à¦¨à¦¿à¦°à¦¾à¦ªà¦¦à¦­à¦¾à¦¬à§‡ à¦°à¦¿à¦…à§à¦¯à¦¾à¦•à¦¶à¦¨ à¦ªà¦¾à¦ à¦¾à¦¯à¦¼"""
    try:
        await client.send_reaction(chat_id=message.chat.id, message_id=message.id, emoji=emoji)
    except Exception:
        pass


async def ensure_assistant(chat_id: int, status_msg):
    """à¦¨à¦¿à¦¶à§à¦šà¦¿à¦¤ à¦•à¦°à§‡ Assistant à¦—à§à¦°à§à¦ªà§‡ à¦†à¦›à§‡"""
    try:
        member = await assistant.get_chat_member(chat_id, (await assistant.get_me()).id)
        LOGGER.info(f"âœ… Assistant already in {chat_id} (status: {member.status})")
        return True
    except Exception as e:
        LOGGER.warning(f"Assistant not in group {chat_id}: {e}")

    # à§§à¦® à¦šà§‡à¦·à§à¦Ÿà¦¾: invite link à¦¦à¦¿à¦¯à¦¼à§‡ join
    try:
        invite = await app.export_chat_invite_link(chat_id)
        LOGGER.info(f"ðŸ“¨ Joining with invite: {invite}")
        await assistant.join_chat(invite)
        await asyncio.sleep(3)
        LOGGER.info(f"âœ… Assistant joined {chat_id}")
        return True
    except Exception as e2:
        LOGGER.warning(f"Invite join failed: {e2}")

    # à§¨à¦¯à¦¼ à¦šà§‡à¦·à§à¦Ÿà¦¾: chat ID à¦¦à¦¿à¦¯à¦¼à§‡ à¦¸à¦°à¦¾à¦¸à¦°à¦¿ join
    try:
        chat = await app.get_chat(chat_id)
        if chat.username:
            await assistant.join_chat(chat.username)
            await asyncio.sleep(3)
            LOGGER.info(f"âœ… Assistant joined via username @{chat.username}")
            return True
    except Exception as e3:
        LOGGER.warning(f"Username join failed: {e3}")

    error_msg = (
        "âŒ **Assistant à¦—à§à¦°à§à¦ªà§‡ à¦¯à§‹à¦— à¦¹à¦¤à§‡ à¦ªà¦¾à¦°à§‡à¦¨à¦¿!**\n\n"
        "ðŸ”§ **à¦¸à¦®à¦¾à¦§à¦¾à¦¨:**\n"
        "1ï¸âƒ£ Assistant à¦…à§à¦¯à¦¾à¦•à¦¾à¦‰à¦¨à§à¦Ÿà¦•à§‡ **manually** à¦—à§à¦°à§à¦ªà§‡ add à¦•à¦°à§à¦¨\n"
        "2ï¸âƒ£ à¦¬à¦Ÿà¦•à§‡ **admin** à¦•à¦°à§à¦¨ (Invite Users permission à¦¦à¦¿à¦¨)\n"
        "3ï¸âƒ£ à¦†à¦¬à¦¾à¦° `/play` à¦•à¦°à§à¦¨"
    )
    LOGGER.error(f"âŒ All join attempts failed for {chat_id}")
    await status_msg.edit(error_msg)
    return False


async def _play(client, message: Message, video: bool):
    """ðŸŽµ à¦—à¦¾à¦¨/à¦­à¦¿à¦¡à¦¿à¦“ à¦ªà§à¦²à§‡ à¦•à¦°à¦¾à¦° à¦®à§‚à¦² à¦«à¦¾à¦‚à¦¶à¦¨"""
    await safe_react(client, message, config.random_emoji())

    cmd_name = "vplay" if video else "play"

    # à¦•à¦®à¦¾à¦¨à§à¦¡ à¦šà§‡à¦•
    if len(message.command) < 2 and not message.reply_to_message:
        return await message.reply_text(
            f"âŒ **à¦—à¦¾à¦¨à§‡à¦° à¦¨à¦¾à¦® à¦¦à¦¾à¦“!**\n\n"
            f"à¦‰à¦¦à¦¾à¦¹à¦°à¦£: `/{cmd_name} tum hi ho`"
        )

    # à¦—à¦¾à¦¨à§‡à¦° à¦¨à¦¾à¦®
    query = (
        " ".join(message.command[1:])
        if len(message.command) > 1
        else (message.reply_to_message.text or "")
    )

    status = await message.reply_text("ðŸ”Ž **à¦–à§à¦à¦œà¦›à¦¿...**")

    try:
        loop = asyncio.get_event_loop()

        # Step 1: à¦¸à¦¾à¦°à§à¦š
        LOGGER.info(f"ðŸ” Searching: {query}")
        try:
            info = await asyncio.wait_for(
                loop.run_in_executor(None, yt_search, query),
                timeout=15
            )
        except asyncio.TimeoutError:
            return await status.edit("â± à¦¸à¦¾à¦°à§à¦š à¦Ÿà¦¾à¦‡à¦®à¦†à¦‰à¦Ÿ à¦¹à¦¯à¦¼à§‡à¦›à§‡à¥¤ à¦†à¦¬à¦¾à¦° à¦šà§‡à¦·à§à¦Ÿà¦¾ à¦•à¦°à§à¦¨à¥¤")
        except Exception as e:
            LOGGER.error(f"Search error: {e}")
            return await status.edit(f"âŒ à¦¸à¦¾à¦°à§à¦š à¦¬à§à¦¯à¦°à§à¦¥: `{str(e)[:80]}`")

        if not info:
            return await status.edit(f"âŒ '{query}' à¦–à§à¦à¦œà§‡ à¦ªà¦¾à¦“à¦¯à¦¼à¦¾ à¦¯à¦¾à¦¯à¦¼à¦¨à¦¿à¥¤ à¦…à¦¨à§à¦¯ à¦¨à¦¾à¦® à¦¦à¦¿à¦¨à¥¤")

        # Step 2: Status à¦†à¦ªà¦¡à§‡à¦Ÿ
        icon = "ðŸŽ¬" if video else "ðŸŽµ"
        await status.edit(
            f"ðŸ“¥ **à¦¡à¦¾à¦‰à¦¨à¦²à§‹à¦¡ à¦¹à¦šà§à¦›à§‡...**\n\n"
            f"{icon} `{info['title'][:50]}`...\n"
            f"â± `{fmt_dur(info['duration'])}`\n\n"
            f"â³ à¦…à¦ªà§‡à¦•à§à¦·à¦¾ à¦•à¦°à§à¦¨..."
        )

        # Step 3: Assistant à¦¨à¦¿à¦¶à§à¦šà¦¿à¦¤ + à¦¡à¦¾à¦‰à¦¨à¦²à§‹à¦¡ (à¦¸à¦®à¦¾à¦¨à§à¦¤à¦°à¦¾à¦²)
        LOGGER.info(f"ðŸ”— Ensuring assistant in {message.chat.id}")
        assistant_task = ensure_assistant(message.chat.id, status)

        LOGGER.info(f"ðŸ’¾ Downloading: {info['link']}")
        download_task = loop.run_in_executor(None, download_media, info["link"], video)

        assistant_ok, media_path = await asyncio.gather(
            assistant_task,
            download_task,
            return_exceptions=True
        )

        # à¦à¦°à¦° à¦šà§‡à¦•
        if isinstance(assistant_ok, Exception):
            LOGGER.error(f"Assistant error: {assistant_ok}")
            return await status.edit("âŒ Assistant à¦¸à¦‚à¦¯à§‹à¦— à¦¬à§à¦¯à¦°à§à¦¥à¥¤ STRING_SESSION à¦šà§‡à¦• à¦•à¦°à§à¦¨à¥¤")

        if isinstance(media_path, Exception):
            LOGGER.error(f"Download error: {media_path}")
            return await status.edit(f"âŒ à¦¡à¦¾à¦‰à¦¨à¦²à§‹à¦¡ à¦¬à§à¦¯à¦°à§à¦¥: {str(media_path)[:80]}")

        if not assistant_ok:
            return

        if not media_path:
            return await status.edit("âŒ à¦®à¦¿à¦¡à¦¿à¦¯à¦¼à¦¾ à¦«à¦¾à¦‡à¦² à¦ªà¦¾à¦“à¦¯à¦¼à¦¾ à¦¯à¦¾à¦¯à¦¼à¦¨à¦¿")

        # Step 4: à¦­à¦¯à¦¼à§‡à¦¸ à¦šà§à¦¯à¦¾à¦Ÿà§‡ à¦¸à§à¦Ÿà§à¦°à¦¿à¦®
        LOGGER.info(f"ðŸŽš Streaming to {message.chat.id}: {media_path}")
        try:
            if video:
                stream = MediaStream(media_path, video_flags=MediaStream.Flags.AUTO_DETECT)
            else:
                stream = MediaStream(media_path, video_flags=MediaStream.Flags.IGNORE)

            await calls.play(message.chat.id, stream)
            ACTIVE_CHATS[message.chat.id] = info
            LOGGER.info(f"âœ… Playing in {message.chat.id}")

        except Exception as e:
            error_str = str(e).lower()
            LOGGER.error(f"Play error: {e}")

            if "no active group call" in error_str or "group_call_invalid" in error_str:
                await status.edit(
                    "âŒ **Voice Chat à¦šà¦¾à¦²à§ à¦¨à§‡à¦‡!**\n\n"
                    "ðŸ”§ **à¦¸à¦®à¦¾à¦§à¦¾à¦¨:**\n"
                    "1ï¸âƒ£ à¦—à§à¦°à§à¦ªà§‡à¦° à¦¨à¦¾à¦®à§‡ à¦•à§à¦²à¦¿à¦• à¦•à¦°à§à¦¨\n"
                    "2ï¸âƒ£ â‹® à¦®à§‡à¦¨à§ à¦¥à§‡à¦•à§‡ **'Voice Chat'** à¦¬à¦¾ **'Video Chat'** à¦¶à§à¦°à§ à¦•à¦°à§à¦¨\n"
                    "3ï¸âƒ£ Voice Chat à¦šà¦¾à¦²à§ à¦¹à¦²à§‡ à¦†à¦¬à¦¾à¦° `/play` à¦¦à¦¿à¦¨\n\n"
                    "âš ï¸ **à¦—à§à¦°à§à¦¤à§à¦¬à¦ªà§‚à¦°à§à¦£:** Voice Chat **à¦†à¦ªà¦¨à¦¾à¦•à§‡** à¦¶à§à¦°à§ à¦•à¦°à¦¤à§‡ à¦¹à¦¬à§‡, à¦¬à¦Ÿ à¦¨à¦¿à¦œà§‡ à¦¶à§à¦°à§ à¦•à¦°à¦¤à§‡ à¦ªà¦¾à¦°à§‡ à¦¨à¦¾à¥¤"
                )
            elif "not found" in error_str or "chat_admin_required" in error_str:
                await status.edit(
                    "âŒ **Assistant-à¦à¦° permission à¦¨à§‡à¦‡!**\n\n"
                    "ðŸ”§ **à¦¸à¦®à¦¾à¦§à¦¾à¦¨:**\n"
                    "1ï¸âƒ£ Assistant à¦…à§à¦¯à¦¾à¦•à¦¾à¦‰à¦¨à§à¦Ÿà¦•à§‡ à¦—à§à¦°à§à¦ªà§‡ **admin** à¦•à¦°à§à¦¨\n"
                    "2ï¸âƒ£ **Manage Voice Chats** permission à¦¦à¦¿à¦¨\n"
                    "3ï¸âƒ£ à¦†à¦¬à¦¾à¦° `/play` à¦¦à¦¿à¦¨"
                )
            else:
                await status.edit(
                    f"âŒ **à¦¸à§à¦Ÿà§à¦°à¦¿à¦®à¦¿à¦‚ à¦¬à§à¦¯à¦°à§à¦¥:** `{str(e)[:100]}`\n\n"
                    "ðŸ”§ **à¦šà§‡à¦·à§à¦Ÿà¦¾ à¦•à¦°à§à¦¨:**\n"
                    "âœ“ `/stop` à¦•à¦°à§‡ à¦†à¦¬à¦¾à¦° `/play` à¦•à¦°à§à¦¨\n"
                    "âœ“ Voice Chat à¦¬à¦¨à§à¦§ à¦•à¦°à§‡ à¦†à¦¬à¦¾à¦° à¦šà¦¾à¦²à§ à¦•à¦°à§à¦¨\n"
                    "âœ“ Assistant à¦—à§à¦°à§à¦ªà§‡ à¦†à¦›à§‡ à¦•à¦¿à¦¨à¦¾ à¦šà§‡à¦• à¦•à¦°à§à¦¨"
                )
            return

        # Step 5: à¦¸à¦¾à¦«à¦²à§à¦¯à§‡à¦° à¦®à§‡à¦¸à§‡à¦œ
        await status.delete()
        caption = (
            f"â•­â”€â”€â”€â€ âœ¦ â€â”€â”€â”€â•®\n"
            f"  {icon} **à¦à¦–à¦¨ {'à¦­à¦¿à¦¡à¦¿à¦“' if video else 'à¦—à¦¾à¦¨'} à¦¬à¦¾à¦œà¦›à§‡**\n"
            f"â•°â”€â”€â”€â€ âœ¦ â€â”€â”€â”€â•¯\n\n"
            f"ðŸŽµ **à¦¶à¦¿à¦°à§‹à¦¨à¦¾à¦®:** {info['title']}\n"
            f"â± **à¦¸à¦®à¦¯à¦¼:** `{fmt_dur(info['duration'])}`\n"
            f"ðŸ“º **à¦šà§à¦¯à¦¾à¦¨à§‡à¦²:** {info['channel']}\n"
            f"ðŸ™‹ **à¦…à¦¨à§à¦°à§‹à¦§à¦•à¦¾à¦°à§€:** {message.from_user.mention}\n\n"
            f"â–«ï¸ â¸ `/pause` â–¶ï¸ `/resume` â­ `/skip` ðŸ›‘ `/stop`"
        )
        try:
            await message.reply_photo(photo=info["thumb"], caption=caption)
        except Exception:
            await message.reply_text(caption)

        # Sticker
        try:
            await asyncio.sleep(0.3)
            await message.reply_sticker(config.random_play_sticker())
        except Exception:
            pass

    except Exception as e:
        LOGGER.error(f"Play function error: {e}")
        await status.edit(f"âŒ à¦…à¦ªà§à¦°à¦¤à§à¦¯à¦¾à¦¶à¦¿à¦¤ à¦¤à§à¦°à§à¦Ÿà¦¿: {str(e)[:100]}")


@app.on_message(filters.command(["play", "p"]) & filters.group)
async def play_cmd(client, message: Message):
    """ðŸŽµ à¦…à¦¡à¦¿à¦“ à¦ªà§à¦²à§‡ à¦•à¦°à§à¦¨"""
    await _play(client, message, video=False)


@app.on_message(filters.command(["vplay", "vp"]) & filters.group)
async def vplay_cmd(client, message: Message):
    """ðŸŽ¬ à¦­à¦¿à¦¡à¦¿à¦“ à¦ªà§à¦²à§‡ à¦•à¦°à§à¦¨"""
    await _play(client, message, video=True)
