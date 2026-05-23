import time
import shutil
from pyrogram import filters
from pyrogram.types import Message

import config
from MusicBangla import app
from MusicBangla.database import stats


@app.on_message(filters.command("ping"))
async def ping_cmd(client, message: Message):
    start = time.time()
    msg = await message.reply_text("🏓 <b>পিং চেক করছি...</b>")
    try:
        await client.send_reaction(chat_id=message.chat.id, message_id=message.id, emoji="⚡")
    except Exception:
        pass
    end = time.time()
    latency = round((end - start) * 1000, 2)
    users, chats = await stats()
    await msg.edit(
        f"╭───❀ ✦ ❀───╮\n"
        f"   ⚡ <b>পিং রিপোর্ট</b>\n"
        f"╰───❀ ✦ ❀───╯\n\n"
        f"🏓 <b>লেটেন্সি:</b> <code>{latency} ms</code>\n"
        f"👥 <b>মোট ইউজার:</b> <code>{users}</code>\n"
        f"💬 <b>মোট গ্রুপ:</b> <code>{chats}</code>\n"
        f"🤖 <b>স্ট্যাটাস:</b> অনলাইন ✅\n\n"
        f"💝 মালিক: @{config.OWNER_USERNAME}"
    )


@app.on_message(filters.command("debug") & filters.user(config.OWNER_ID))
async def debug_cmd(client, message: Message):
    """Owner-only debug command — yt-dlp version ও config check"""
    import yt_dlp
    import subprocess

    lines = []
    lines.append(f"🔧 <b>Debug Info</b>\n")
    lines.append(f"📦 <b>yt-dlp:</b> <code>{yt_dlp.version.__version__}</code>")

    # Node.js check
    node = shutil.which("node")
    if node:
        try:
            nv = subprocess.check_output(["node", "--version"], timeout=5).decode().strip()
            lines.append(f"📗 <b>Node.js:</b> <code>{nv}</code> ({node})")
        except Exception:
            lines.append(f"📗 <b>Node.js:</b> found at {node} (version unknown)")
    else:
        lines.append("📗 <b>Node.js:</b> ❌ না পাওয়া গেছে")

    # yt-dlp format test
    try:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best",
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ", download=False)
            fmt = info.get("format", "?")
            lines.append(f"🎵 <b>Format test:</b> ✅ <code>{fmt}</code>")
    except Exception as e:
        lines.append(f"🎵 <b>Format test:</b> ❌ <code>{str(e)[:100]}</code>")

    # commit info
    lines.append(f"\n📌 <b>Build:</b> <code>v8-format-fix</code>")

    await message.reply_text("\n".join(lines))
