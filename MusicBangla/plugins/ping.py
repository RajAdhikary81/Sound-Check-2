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
    """Owner-only debug — yt-dlp version, player clients, API status"""
    import yt_dlp
    import subprocess
    import httpx

    lines = []
    lines.append(f"🔧 <b>Debug Info</b>\n")
    lines.append(f"📦 <b>yt-dlp:</b> <code>{yt_dlp.version.__version__}</code>")

    # Node.js check
    node = shutil.which("node")
    if node:
        try:
            nv = subprocess.check_output(["node", "--version"], timeout=5).decode().strip()
            lines.append(f"📗 <b>Node.js:</b> <code>{nv}</code>")
        except Exception:
            lines.append(f"📗 <b>Node.js:</b> found (version unknown)")
    else:
        lines.append("📗 <b>Node.js:</b> ❌ না পাওয়া গেছে")

    # yt-dlp format test with android_vr
    try:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best",
            "no_check_formats": True,
            "extractor_args": {"youtube": {"player_client": ["android_vr"]}},
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ", download=False)
            fmt = info.get("format", "?")
            url_ok = "✅" if info.get("url") else "⚠️ no url"
            lines.append(f"🎵 <b>yt-dlp test (android_vr):</b> {url_ok} <code>{fmt}</code>")
    except Exception as e:
        lines.append(f"🎵 <b>yt-dlp test:</b> ❌ <code>{str(e)[:80]}</code>")

    # Cobalt API test
    try:
        with httpx.Client(timeout=10) as hc:
            r = hc.get("https://cobalt-api.ayo.tf/")
            lines.append(f"🌐 <b>Cobalt API:</b> {'✅' if r.status_code < 500 else '❌'} HTTP {r.status_code}")
    except Exception as e:
        lines.append(f"🌐 <b>Cobalt API:</b> ❌ <code>{str(e)[:50]}</code>")

    # Piped API test
    try:
        with httpx.Client(timeout=10) as hc:
            r = hc.get("https://pipedapi.kavin.rocks/streams/dQw4w9WgXcQ")
            if r.status_code == 200:
                data = r.json()
                n_audio = len(data.get("audioStreams", []))
                lines.append(f"🌐 <b>Piped API:</b> ✅ {n_audio} audio streams")
            else:
                lines.append(f"🌐 <b>Piped API:</b> ❌ HTTP {r.status_code}")
    except Exception as e:
        lines.append(f"🌐 <b>Piped API:</b> ❌ <code>{str(e)[:50]}</code>")

    lines.append(f"\n📌 <b>Build:</b> <code>v10-4layer-fallback</code>")
    lines.append(f"🛡 <b>Features:</b> 4-layer fallback, rate-limit, anti-flood, input sanitize")

    await message.reply_text("\n".join(lines))


@app.on_message(filters.command("sysinfo") & filters.user(config.OWNER_ID))
async def sysinfo_cmd(client, message: Message):
    """Owner-only system info"""
    import platform
    import psutil

    try:
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        text = (
            f"🖥 <b>System Info</b>\n\n"
            f"🐍 <b>Python:</b> <code>{platform.python_version()}</code>\n"
            f"💻 <b>OS:</b> <code>{platform.system()} {platform.release()}</code>\n"
            f"⚙️ <b>CPU:</b> <code>{cpu}%</code>\n"
            f"🧠 <b>RAM:</b> <code>{mem.used // (1024**2)}MB / {mem.total // (1024**2)}MB ({mem.percent}%)</code>\n"
            f"💾 <b>Disk:</b> <code>{disk.used // (1024**2)}MB / {disk.total // (1024**2)}MB ({disk.percent}%)</code>\n"
        )
        await message.reply_text(text)
    except ImportError:
        await message.reply_text("❌ <code>psutil</code> not installed")
    except Exception as e:
        await message.reply_text(f"❌ Error: <code>{e}</code>")
