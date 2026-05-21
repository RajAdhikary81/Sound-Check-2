import asyncio
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
from MusicBangla import app
from MusicBangla.database import add_user, add_chat


def main_buttons():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ গ্রুপে যোগ করো", url=f"https://t.me/{app.me.username if app.me else 'YourBot'}?startgroup=true")],
            [
                InlineKeyboardButton("📢 চ্যানেল", url=config.SUPPORT_CHANNEL),
                InlineKeyboardButton("💬 সাপোর্ট", url=config.SUPPORT_GROUP),
            ],
            [
                InlineKeyboardButton("🎮 গেম খেলো", callback_data="games_menu"),
                InlineKeyboardButton("❓ হেল্প", callback_data="help_menu"),
            ],
            [
                InlineKeyboardButton("👨‍💻 মালিক", url=f"https://t.me/{config.OWNER_USERNAME}"),
                InlineKeyboardButton("📁 সোর্স", url=config.GITHUB_URL),
            ],
        ]
    )


async def safe_react(client, message, emoji):
    try:
        await client.send_reaction(chat_id=message.chat.id, message_id=message.id, emoji=emoji)
    except Exception:
        pass


async def safe_sticker(message, sticker_id):
    try:
        await message.reply_sticker(sticker_id)
    except Exception:
        pass


@app.on_message(filters.command("start") & filters.private)
async def start_private(client, message: Message):
    await add_user(message.from_user.id)
    await safe_react(client, message, config.random_emoji())

    caption = (
        f"╭───❀ ✦ ❀───╮\n"
        f"   🎶 <b>স্বাগতম {message.from_user.mention}!</b>\n"
        f"╰───❀ ✦ ❀───╯\n\n"
        f"আমি <b>{app.me.first_name}</b> — তোমার নিজস্ব বাংলা মিউজিক বট 🎧\n\n"
        f"আমাকে যেকোনো গ্রুপে অ্যাডমিন করে যোগ করো, ভয়েস চ্যাটে গান বাজাও, গেম খেলো এবং সবাইকে welcome করো।\n\n"
        f"✨ <b>প্রধান কমান্ডস:</b>\n"
        f"▫️ <code>/play গানের নাম</code> — গান চালাও\n"
        f"▫️ <code>/pause</code> ⏸  <code>/resume</code> ▶️  <code>/skip</code> ⏭  <code>/stop</code> 🛑\n"
        f"▫️ <code>/tagall</code> — সবাইকে mention করো\n"
        f"▫️ <code>/games</code> — গেম মেনু\n"
        f"▫️ <code>/ping</code> — বটের স্ট্যাটাস\n\n"
        f"💝 <b>মালিক:</b> @{config.OWNER_USERNAME}\n"
        f"📢 <b>চ্যানেল:</b> {config.SUPPORT_CHANNEL}"
    )
    await message.reply_photo(
        photo=config.random_image(),
        caption=caption,
        reply_markup=main_buttons(),
    )
    await asyncio.sleep(0.3)
    await safe_sticker(message, config.random_start_sticker())

    try:
        await app.send_message(
            chat_id=config.LOG_GROUP_ID,
            text=(
                f"🎉 নতুন ইউজার!\n\n"
                f"👤 {message.from_user.mention}\n"
                f"🆔 <code>{message.from_user.id}</code>\n"
                f"📛 @{message.from_user.username}"
            ),
        )
    except Exception:
        pass


@app.on_message(filters.command("start") & filters.group)
async def start_group(client, message: Message):
    await add_chat(message.chat.id)
    await safe_react(client, message, config.random_emoji())

    caption = (
        f"🎶 <b>হ্যালো {message.chat.title}!</b>\n\n"
        f"আমি <b>{app.me.first_name}</b> — তোমাদের বাংলা মিউজিক বট 🎧\n\n"
        f"▫️ <code>/play গানের নাম</code> — গান চালাও\n"
        f"▫️ <code>/tagall</code> — সবাইকে mention করো\n"
        f"▫️ <code>/games</code> — গেম খেলো\n\n"
        f"আমাকে অবশ্যই <b>অ্যাডমিন</b> করো (Voice Chat manage permission সহ)"
    )
    await message.reply_photo(photo=config.random_image(), caption=caption, reply_markup=main_buttons())


@app.on_message(filters.command("help"))
async def help_cmd(client, message: Message):
    text = (
        "📚 <b>সব কমান্ড লিস্ট</b>\n\n"
        "🎵 <b>মিউজিক:</b>\n"
        "▫️ <code>/play গানের নাম</code> — গান বাজাও\n"
        "▫️ <code>/pause</code> ⏸ <code>/resume</code> ▶️\n"
        "▫️ <code>/skip</code> ⏭ <code>/stop</code> 🛑\n\n"
        "👥 <b>গ্রুপ টুলস:</b>\n"
        "▫️ <code>/tagall [মেসেজ]</code> — সবাইকে mention করো\n"
        "▫️ <code>/admins</code> — গ্রুপের admin-দের mention\n"
        "▫️ <code>/cancel</code> — চলমান tag বাতিল\n\n"
        "🎮 <b>গেম:</b>\n"
        "▫️ <code>/games</code> — সব গেমের মেনু\n"
        "▫️ <code>/ttt</code> — Tic-Tac-Toe\n"
        "▫️ <code>/truth</code> — Truth প্রশ্ন\n"
        "▫️ <code>/dare</code> — Dare চ্যালেঞ্জ\n"
        "▫️ <code>/rps</code> — Rock Paper Scissors\n"
        "▫️ <code>/quiz</code> — কুইজ\n"
        "▫️ <code>/8ball প্রশ্ন</code> — ম্যাজিক ৮-বল\n"
        "▫️ <code>/flip</code> — Coin flip\n"
        "▫️ <code>/dice</code> — Dice roll\n\n"
        "ℹ️ <b>অন্যান্য:</b>\n"
        "▫️ <code>/ping</code> — স্ট্যাটাস\n"
        "▫️ <code>/start</code> — শুরু"
    )
    await message.reply_text(text, reply_markup=main_buttons())


@app.on_message(filters.new_chat_members, group=-1)
async def welcome_handler(client, message: Message):
    for member in message.new_chat_members:
        # বট নিজেই গ্রুপে যোগ হলে
        if member.id == app.me.id:
            await add_chat(message.chat.id)
            caption = (
                f"🎉 <b>ধন্যবাদ {message.from_user.first_name}!</b>\n\n"
                f"আমাকে <b>{message.chat.title}</b>-এ যোগ করার জন্য ❤️\n\n"
                f"✅ আমাকে <b>Admin</b> করো (Manage Voice Chats permission দাও)\n"
                f"✅ Assistant অ্যাকাউন্ট গ্রুপে যোগ করো\n"
                f"▫️ তারপর <code>/play গানের নাম</code> দিয়ে শুরু!\n\n"
                f"🎮 <code>/games</code> দিয়ে গেম খেলো | 👥 <code>/tagall</code> দিয়ে সবাইকে ডাকো"
            )
            try:
                await message.reply_photo(photo=config.random_image(), caption=caption, reply_markup=main_buttons())
                await safe_sticker(message, config.random_start_sticker())
            except Exception:
                await message.reply_text(caption)
            continue

        # নতুন user welcome
        if member.is_bot:
            continue
        await add_user(member.id)
        try:
            caption = (
                f"🌸 <b>স্বাগতম {member.mention}!</b> 🌸\n\n"
                f"<b>{message.chat.title}</b>-এ তোমাকে অভিনন্দন 💝\n\n"
                f"🎵 <code>/play গানের নাম</code> — গান শোনো\n"
                f"🎮 <code>/games</code> — গেম খেলো\n"
                f"👥 <code>/tagall</code> — সবার সাথে কথা বলো\n\n"
                f"আনন্দে থাকো, ভালোবেসে যাও 🎶"
            )
            await message.reply_photo(photo=config.random_image(), caption=caption)
            await safe_react(client, message, config.random_emoji())
        except Exception:
            try:
                await message.reply_text(f"🌸 স্বাগতম {member.mention}! 💝")
            except Exception:
                pass
