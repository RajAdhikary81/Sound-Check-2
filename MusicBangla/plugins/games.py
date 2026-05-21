"""
গেম plugin — বিভিন্ন ধরনের গেম:
- /games — গেমের মেনু
- /ttt — Tic-Tac-Toe (2-player)
- /truth — random truth
- /dare — random dare
- /td — Truth or Dare (random)
- /rps — Rock Paper Scissors
- /quiz — কুইজ
- /8ball <প্রশ্ন> — ম্যাজিক ৮-বল
- /flip — Coin flip
- /dice — Dice roll
"""
import random
from pyrogram import filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from MusicBangla import app


TRUTHS = [
    "তোমার সবচেয়ে লজ্জাজনক স্মৃতি কী?",
    "এই গ্রুপের কাকে তুমি সবচেয়ে বেশি পছন্দ করো?",
    "তোমার শেষ মিথ্যা কথা কী ছিল?",
    "জীবনে কাকে সবচেয়ে বেশি miss করো?",
    "তোমার গোপন crush এর নাম কী?",
    "শেষ কবে কেঁদেছিলে এবং কেন?",
    "তোমার সবচেয়ে বড় ভয় কী?",
    "কোন কাজটা করে তুমি সবচেয়ে বেশি অনুতপ্ত?",
    "তোমার phone-এর last search কী ছিল?",
    "তুমি কি কখনো parents-কে মিথ্যা বলেছ? কী মিথ্যা?",
    "তোমার biggest dream কী?",
    "তোমার একটা bad habit বলো।",
    "শেষ কাকে \"I love you\" বলেছিলে?",
    "তোমার জীবনের সবচেয়ে অদ্ভুত স্বপ্ন কী ছিল?",
    "তুমি কি কখনো cheating করেছ পরীক্ষায়?",
]

DARES = [
    "পরের ৫ মিনিট শুধু shayari তে কথা বলো 🌹",
    "তোমার গলায় গান গেয়ে ভয়েস মেসেজ পাঠাও 🎤",
    "তোমার ফোনের wallpaper গ্রুপে পাঠাও 📱",
    "একটা হাসির selfie পাঠাও 🤪",
    "তোমার crush-কে \"hi\" মেসেজ দাও এবং screenshot পাঠাও 😈",
    "একটা joke বলো — সবাই হাসলে pass!",
    "তোমার ভয়েসে \"আমি একটা গাধা\" বলে রেকর্ড পাঠাও 🐴",
    "Last call list-এর প্রথম জনকে \"I love you\" বলে call দাও 📞",
    "৩ মিনিট গ্রুপে কোনো reply না করে চুপ থাকো 🤫",
    "তোমার নাম reverse করে গ্রুপে পাঠাও 🔄",
    "পরের ৫টা মেসেজে কোনো vowel ব্যবহার কোরো না 🚫",
    "তোমার ছোটবেলার একটা ছবি পাঠাও 👶",
    "Group-এর next member কে compliment দাও 💝",
    "তোমার phone gallery-র last image পাঠাও 🖼",
]

EIGHT_BALL = [
    "হ্যাঁ, একদম! ✅",
    "না, কখনোই না। ❌",
    "হতে পারে... 🤔",
    "তারকারা বলছে — হ্যাঁ! ⭐",
    "এখন না, পরে। ⏳",
    "অবশ্যই! 💯",
    "ভুলে যাও। 🚫",
    "ভাগ্য তোমার সাথে আছে 🍀",
    "আমি নিশ্চিত না, আবার জিজ্ঞেস করো 🔮",
    "Definitely yes ✨",
    "Sorry, এটা সম্ভব না 😔",
    "হ্যাঁ — কিন্তু সাবধানে! ⚠️",
]

QUIZ = [
    {"q": "বাংলাদেশের রাজধানী কী?", "options": ["চট্টগ্রাম", "ঢাকা", "খুলনা", "রাজশাহী"], "ans": 1},
    {"q": "রবীন্দ্রনাথ ঠাকুর কত সালে নোবেল পান?", "options": ["1911", "1913", "1915", "1920"], "ans": 1},
    {"q": "সূর্য পূর্ব দিকে ওঠে — সত্য না মিথ্যা?", "options": ["সত্য", "মিথ্যা", "জানি না", "কখনো না"], "ans": 0},
    {"q": "পদ্মা সেতু কত কিমি লম্বা?", "options": ["৪.১৫", "৬.১৫", "৮.১০", "১০.০০"], "ans": 1},
    {"q": "\"বিদ্রোহী\" কবিতার রচয়িতা কে?", "options": ["জীবনানন্দ", "নজরুল", "জসীমউদ্দীন", "রবীন্দ্রনাথ"], "ans": 1},
    {"q": "মানুষের শরীরে কতটি হাড় থাকে?", "options": ["১৮৬", "২০৬", "২৫০", "৩০০"], "ans": 1},
    {"q": "World Cup 2023 কে জিতেছিল?", "options": ["India", "Australia", "England", "Pakistan"], "ans": 1},
    {"q": "Python কে তৈরি করেন?", "options": ["Linus", "Guido van Rossum", "Larry Page", "Bill Gates"], "ans": 1},
]

TTT_GAMES = {}
RPS_CHOICES = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}


def games_menu_kb():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⭕ Tic-Tac-Toe", callback_data="game_ttt"),
                InlineKeyboardButton("🎲 Dice", callback_data="game_dice"),
            ],
            [
                InlineKeyboardButton("🎯 Truth", callback_data="game_truth"),
                InlineKeyboardButton("🔥 Dare", callback_data="game_dare"),
            ],
            [
                InlineKeyboardButton("✊ Rock-Paper-Scissors", callback_data="game_rps_menu"),
            ],
            [
                InlineKeyboardButton("🧠 Quiz", callback_data="game_quiz"),
                InlineKeyboardButton("🪙 Coin Flip", callback_data="game_flip"),
            ],
            [
                InlineKeyboardButton("🔮 8-Ball", callback_data="game_8ball_info"),
            ],
        ]
    )


@app.on_message(filters.command(["games", "game"]))
async def games_menu(client, message: Message):
    text = (
        "🎮 <b>গেম মেনু</b>\n\n"
        "নিচের যেকোনো গেম বেছে নাও অথবা কমান্ড দিয়ে চালাও:\n\n"
        "▫️ <code>/ttt</code> — Tic-Tac-Toe\n"
        "▫️ <code>/truth</code> | <code>/dare</code> | <code>/td</code>\n"
        "▫️ <code>/rps</code> — Rock Paper Scissors\n"
        "▫️ <code>/quiz</code> — কুইজ\n"
        "▫️ <code>/8ball &lt;প্রশ্ন&gt;</code>\n"
        "▫️ <code>/flip</code> — Coin flip\n"
        "▫️ <code>/dice</code> — Dice roll"
    )
    await message.reply_text(text, reply_markup=games_menu_kb())


@app.on_callback_query(filters.regex(r"^games_menu$|^help_menu$"))
async def cb_open_games(client, cq: CallbackQuery):
    if cq.data == "help_menu":
        await cq.message.reply_text("⬇️ <code>/help</code> দাও সব কমান্ড দেখতে।")
        return await cq.answer()
    await cq.message.reply_text("🎮 <b>গেম মেনু</b>\nনিচ থেকে বেছে নাও:", reply_markup=games_menu_kb())
    await cq.answer()


@app.on_message(filters.command("truth"))
async def truth_cmd(client, message: Message):
    await message.reply_text(f"🎯 <b>Truth:</b>\n\n<i>{random.choice(TRUTHS)}</i>")


@app.on_message(filters.command("dare"))
async def dare_cmd(client, message: Message):
    await message.reply_text(f"🔥 <b>Dare:</b>\n\n<i>{random.choice(DARES)}</i>")


@app.on_message(filters.command(["td", "truthordare"]))
async def td_cmd(client, message: Message):
    if random.random() < 0.5:
        await message.reply_text(f"🎯 <b>Truth:</b>\n\n<i>{random.choice(TRUTHS)}</i>")
    else:
        await message.reply_text(f"🔥 <b>Dare:</b>\n\n<i>{random.choice(DARES)}</i>")


@app.on_callback_query(filters.regex(r"^game_truth$"))
async def cb_truth(client, cq: CallbackQuery):
    await cq.message.reply_text(f"🎯 <b>Truth:</b>\n\n<i>{random.choice(TRUTHS)}</i>")
    await cq.answer("Truth!")


@app.on_callback_query(filters.regex(r"^game_dare$"))
async def cb_dare(client, cq: CallbackQuery):
    await cq.message.reply_text(f"🔥 <b>Dare:</b>\n\n<i>{random.choice(DARES)}</i>")
    await cq.answer("Dare!")


@app.on_message(filters.command("8ball"))
async def eight_ball_cmd(client, message: Message):
    if len(message.command) < 2 and not message.reply_to_message:
        return await message.reply_text("❓ একটা প্রশ্ন দাও!\nউদাহরণ: <code>/8ball আমি কি ধনী হবো?</code>")
    q = " ".join(message.command[1:]) if len(message.command) > 1 else message.reply_to_message.text
    await message.reply_text(f"🔮 <b>প্রশ্ন:</b> {q}\n\n💫 <b>উত্তর:</b> {random.choice(EIGHT_BALL)}")


@app.on_callback_query(filters.regex(r"^game_8ball_info$"))
async def cb_8ball_info(client, cq: CallbackQuery):
    await cq.answer("/8ball <প্রশ্ন> দিয়ে জিজ্ঞেস করো", show_alert=True)


@app.on_message(filters.command(["flip", "coin"]))
async def flip_cmd(client, message: Message):
    r = random.choice(["🪙 Heads (মাথা)", "🪙 Tails (পট)"])
    await message.reply_text(f"<b>Coin Flip:</b>\n\n{r}")


@app.on_callback_query(filters.regex(r"^game_flip$"))
async def cb_flip(client, cq: CallbackQuery):
    r = random.choice(["🪙 Heads (মাথা)", "🪙 Tails (পট)"])
    await cq.message.reply_text(f"<b>Coin Flip:</b>\n\n{r}")
    await cq.answer()


@app.on_message(filters.command("dice"))
async def dice_cmd(client, message: Message):
    try:
        await message.reply_dice(emoji="🎲")
    except Exception:
        await message.reply_text(f"🎲 তুমি পেয়েছ: <b>{random.randint(1, 6)}</b>")


@app.on_callback_query(filters.regex(r"^game_dice$"))
async def cb_dice(client, cq: CallbackQuery):
    try:
        await cq.message.reply_dice(emoji="🎲")
    except Exception:
        await cq.message.reply_text(f"🎲 তুমি পেয়েছ: <b>{random.randint(1, 6)}</b>")
    await cq.answer()


def rps_kb():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🪨 Rock", callback_data="rps_rock"),
                InlineKeyboardButton("📄 Paper", callback_data="rps_paper"),
                InlineKeyboardButton("✂️ Scissors", callback_data="rps_scissors"),
            ]
        ]
    )


@app.on_message(filters.command("rps"))
async def rps_cmd(client, message: Message):
    await message.reply_text("✊ <b>Rock Paper Scissors</b>\nতোমার পছন্দ:", reply_markup=rps_kb())


@app.on_callback_query(filters.regex(r"^game_rps_menu$"))
async def cb_rps_menu(client, cq: CallbackQuery):
    await cq.message.reply_text("✊ <b>Rock Paper Scissors</b>\nতোমার পছন্দ:", reply_markup=rps_kb())
    await cq.answer()


@app.on_callback_query(filters.regex(r"^rps_(rock|paper|scissors)$"))
async def cb_rps_play(client, cq: CallbackQuery):
    user_choice = cq.data.split("_")[1]
    bot_choice = random.choice(list(RPS_CHOICES.keys()))

    if user_choice == bot_choice:
        result = "🤝 Draw হলো!"
    elif (
        (user_choice == "rock" and bot_choice == "scissors")
        or (user_choice == "paper" and bot_choice == "rock")
        or (user_choice == "scissors" and bot_choice == "paper")
    ):
        result = f"🎉 {cq.from_user.first_name} জিতেছে!"
    else:
        result = "🤖 বট জিতেছে!"

    await cq.message.reply_text(
        f"✊ <b>Rock Paper Scissors</b>\n\n"
        f"👤 {cq.from_user.mention}: {RPS_CHOICES[user_choice]}\n"
        f"🤖 বট: {RPS_CHOICES[bot_choice]}\n\n"
        f"<b>{result}</b>"
    )
    await cq.answer()


@app.on_message(filters.command("quiz"))
async def quiz_cmd(client, message: Message):
    q = random.choice(QUIZ)
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(opt, callback_data=f"quiz_{i}_{q['ans']}")]
            for i, opt in enumerate(q["options"])
        ]
    )
    await message.reply_text(f"🧠 <b>কুইজ:</b>\n\n{q['q']}", reply_markup=kb)


@app.on_callback_query(filters.regex(r"^game_quiz$"))
async def cb_quiz(client, cq: CallbackQuery):
    q = random.choice(QUIZ)
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(opt, callback_data=f"quiz_{i}_{q['ans']}")]
            for i, opt in enumerate(q["options"])
        ]
    )
    await cq.message.reply_text(f"🧠 <b>কুইজ:</b>\n\n{q['q']}", reply_markup=kb)
    await cq.answer()


@app.on_callback_query(filters.regex(r"^quiz_(\d)_(\d)$"))
async def cb_quiz_answer(client, cq: CallbackQuery):
    _, picked, ans = cq.data.split("_")
    picked, ans = int(picked), int(ans)
    if picked == ans:
        await cq.answer("🎉 সঠিক উত্তর!", show_alert=True)
        await cq.message.reply_text(f"✅ {cq.from_user.mention} সঠিক উত্তর দিয়েছে!")
    else:
        await cq.answer("❌ ভুল উত্তর", show_alert=True)


def ttt_kb(board, game_id):
    rows = []
    for r in range(3):
        row = []
        for c in range(3):
            i = r * 3 + c
            cell = board[i] if board[i] else "·"
            row.append(InlineKeyboardButton(cell, callback_data=f"ttt_{game_id}_{i}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("🛑 খেলা শেষ", callback_data=f"ttt_{game_id}_end")])
    return InlineKeyboardMarkup(rows)


def ttt_winner(board):
    lines = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8),
        (0, 3, 6), (1, 4, 7), (2, 5, 8),
        (0, 4, 8), (2, 4, 6),
    ]
    for a, b, c in lines:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    if all(board):
        return "draw"
    return None


@app.on_message(filters.command(["ttt", "tictactoe"]))
async def ttt_cmd(client, message: Message):
    chat_id = message.chat.id
    game = {
        "board": [""] * 9,
        "turn": "❌",
        "players": {"❌": message.from_user, "⭕": None},
        "starter_id": message.from_user.id,
    }
    TTT_GAMES[chat_id] = game
    await message.reply_text(
        f"⭕ <b>Tic-Tac-Toe</b>\n\n"
        f"❌: {message.from_user.mention}\n"
        f"⭕: <i>অপেক্ষা... যেকোনো ঘরে ক্লিক করে জয়েন করো</i>\n\n"
        f"এখন: <b>❌</b>",
        reply_markup=ttt_kb(game["board"], chat_id),
    )


@app.on_callback_query(filters.regex(r"^ttt_(-?\d+)_(\d+|end)$"))
async def cb_ttt(client, cq: CallbackQuery):
    parts = cq.data.split("_")
    game_id = int(parts[1])
    action = parts[2]

    game = TTT_GAMES.get(game_id)
    if not game:
        return await cq.answer("এই গেমটি আর নেই। নতুন করে /ttt দাও।", show_alert=True)

    if action == "end":
        if cq.from_user.id != game["starter_id"]:
            return await cq.answer("শুধু গেম শুরুকারী শেষ করতে পারবে।", show_alert=True)
        TTT_GAMES.pop(game_id, None)
        await cq.message.edit_text("🛑 গেম শেষ হয়েছে।")
        return await cq.answer()

    idx = int(action)
    user = cq.from_user

    if game["players"]["⭕"] is None and user.id != game["players"]["❌"].id:
        game["players"]["⭕"] = user

    p_x = game["players"]["❌"]
    p_o = game["players"]["⭕"]

    if user.id not in [p_x.id, p_o.id if p_o else 0]:
        return await cq.answer("তুমি এই গেমে নেই! নতুন করে /ttt শুরু করো।", show_alert=True)

    expected = p_x if game["turn"] == "❌" else p_o
    if not expected or user.id != expected.id:
        return await cq.answer("তোমার পালা না!", show_alert=True)

    if game["board"][idx]:
        return await cq.answer("এই ঘর ভর্তি!", show_alert=True)

    game["board"][idx] = game["turn"]
    winner = ttt_winner(game["board"])

    if winner == "draw":
        TTT_GAMES.pop(game_id, None)
        await cq.message.edit_text(
            f"⭕ <b>Tic-Tac-Toe</b>\n\nফলাফল: 🤝 <b>Draw!</b>",
            reply_markup=ttt_kb(game["board"], game_id),
        )
        return await cq.answer("Draw!")

    if winner:
        winner_user = p_x if winner == "❌" else p_o
        TTT_GAMES.pop(game_id, None)
        await cq.message.edit_text(
            f"⭕ <b>Tic-Tac-Toe</b>\n\n🎉 <b>{winner}</b> জিতেছে!\nবিজয়ী: {winner_user.mention}",
            reply_markup=ttt_kb(game["board"], game_id),
        )
        return await cq.answer("জিতেছ!")

    game["turn"] = "⭕" if game["turn"] == "❌" else "❌"
    p_o_text = p_o.mention if p_o else "<i>অপেক্ষা...</i>"
    await cq.message.edit_text(
        f"⭕ <b>Tic-Tac-Toe</b>\n\n"
        f"❌: {p_x.mention}\n"
        f"⭕: {p_o_text}\n\n"
        f"এখন: <b>{game['turn']}</b>",
        reply_markup=ttt_kb(game["board"], game_id),
    )
    await cq.answer()
