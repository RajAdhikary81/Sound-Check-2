<p align="center">
  <img src="https://pic-link-bot.lovable.app/i/telegram-1779340031479-5eab5504.jpg" alt="MusicBangla Banner" width="360" style="border-radius: 20px;" />
</p>

<h1 align="center">🎵 MusicBangla — বাংলা মিউজিক বট</h1>

<p align="center">
  <b>An Advanced Telegram Music Bot with Games, Smart Tagging & More</b><br/>
  <i>একটি স্টাইলিশ বাংলা টেলিগ্রাম মিউজিক বট — গান, গেম, মেনশন সবকিছু এক জায়গায়</i>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" /></a>
  <a href="https://docs.pyrogram.org/"><img src="https://img.shields.io/badge/Pyrogram-Fork-FF6F00?style=for-the-badge&logo=telegram&logoColor=white" alt="Pyrogram" /></a>
  <a href="https://github.com/RajSukh81/MusicBangla"><img src="https://img.shields.io/badge/License-Open_Source-00C853?style=for-the-badge&logo=opensourceinitiative&logoColor=white" alt="Open Source" /></a>
  <a href="https://t.me/R4J_81"><img src="https://img.shields.io/badge/Telegram-@R4J__81-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram" /></a>
</p>

<p align="center">
  <a href="https://github.com/RajSukh81/MusicBangla/stargazers"><img src="https://img.shields.io/github/stars/RajSukh81/MusicBangla?style=social" alt="Stars" /></a>
  <a href="https://github.com/RajSukh81/MusicBangla/network/members"><img src="https://img.shields.io/github/forks/RajSukh81/MusicBangla?style=social" alt="Forks" /></a>
  <a href="https://github.com/RajSukh81/MusicBangla"><img src="https://img.shields.io/github/repo-size/RajSukh81/MusicBangla?style=flat-square&color=blueviolet" alt="Repo Size" /></a>
  <a href="https://github.com/RajSukh81/MusicBangla/commits/main"><img src="https://img.shields.io/github/last-commit/RajSukh81/MusicBangla?style=flat-square&color=orange" alt="Last Commit" /></a>
</p>

---

## 🇮🇳 বাংলায় পড়ুন / 🇬🇧 Read in English

> **MusicBangla** হলো একটি ফিচার-সমৃদ্ধ টেলিগ্রাম বট যা **গান বাজানো**, **ভিডিও স্ট্রিম**, **ইন্টারেক্টিভ গেম**, **স্মার্ট ট্যাগিং** এবং আরো অনেক কিছু করতে পারে — সবকিছু বাংলা ও ইংরেজি দুই ভাষায়।

> **MusicBangla** is a feature-rich Telegram bot that can **play music**, **stream video**, run **interactive games**, do **smart tagging**, and much more — all in both Bangla and English.

---

## ✨ Features / ফিচারসমূহ

<table>
<tr>
<td width="50%">

### 🎵 Music & Video / মিউজিক ও ভিডিও
| Command | Description / বর্ণনা |
|---------|----------------------|
| `/play <name>` | Play a song in Voice Chat / ভয়েস চ্যাটে গান বাজাও |
| `/vplay <name>` | Stream video in Voice Chat / ভিডিও স্ট্রিম করো |
| `/pause` | Pause current stream / গান পজ করো |
| `/resume` | Resume paused stream / গান আবার চালু করো |
| `/skip` | Skip to next / পরের গানে যাও |
| `/stop` | Stop & leave VC / স্ট্রিম বন্ধ করো |

</td>
<td width="50%">

### 🎮 Games / গেমসমূহ
| Command | Description / বর্ণনা |
|---------|----------------------|
| `/games` | Open game menu / গেম মেনু খোলো |
| `/ttt` | Tic-Tac-Toe (2 player) / দুইজনে খেলো |
| `/truth` | Random truth question / সত্য প্রশ্ন |
| `/dare` | Random dare challenge / ডেয়ার চ্যালেঞ্জ |
| `/td` | Random truth or dare / সত্য অথবা ডেয়ার |
| `/rps` | Rock Paper Scissors / পাথর কাগজ কাঁচি |
| `/quiz` | Bengali quiz / বাংলা কুইজ |
| `/8ball <question>` | Magic 8-Ball / ম্যাজিক ৮-বল |
| `/flip` | Coin flip / মুদ্রা উল্টাও |
| `/dice` | Roll a dice / ডাইস গড়াও |

</td>
</tr>
<tr>
<td>

### 👥 Smart Tagging / স্মার্ট ট্যাগিং
| Command | Description / বর্ণনা |
|---------|----------------------|
| `/tagall [msg]` | Mention all members / সবাইকে মেনশন করো |
| `/admins` | Mention all admins / সব অ্যাডমিনকে ট্যাগ করো |
| `/cancel` | Cancel ongoing tag / চলমান ট্যাগ বাতিল করো |

</td>
<td>

### ℹ️ Utility / ইউটিলিটি
| Command | Description / বর্ণনা |
|---------|----------------------|
| `/start` | Start the bot / বট শুরু করো |
| `/help` | Show all commands / সব কমান্ড দেখো |
| `/ping` | Check bot latency & stats / বটের স্ট্যাটাস দেখো |

</td>
</tr>
</table>

---

## 🏗️ Architecture / আর্কিটেকচার

```
MusicBangla/
├── config.py              # Bot configuration & env vars
├── Procfile               # Heroku worker process
├── app.json               # Heroku one-click deploy config
├── requirements.txt       # Python dependencies
├── package.json           # Node.js support (FFmpeg)
├── runtime.txt            # Python runtime version
└── MusicBangla/
    ├── __init__.py        # App initialization (bot + assistant + calls)
    ├── __main__.py        # Entry point
    ├── database.py        # MongoDB async database layer
    └── plugins/
        ├── start.py       # /start, /help, welcome messages
        ├── play.py        # /play, /vplay — music & video streaming
        ├── controls.py    # /pause, /resume, /skip, /stop
        ├── games.py       # All 9 interactive games
        ├── mention.py     # /tagall, /admins, /cancel
        └── ping.py        # /ping — latency & stats
```

---

## 🛠️ Tech Stack / প্রযুক্তি

<p align="center">
  <img src="https://img.shields.io/badge/Pyrogram-Telegram_MTProto-2CA5E0?style=flat-square&logo=telegram" />
  <img src="https://img.shields.io/badge/PyTgCalls-Voice_Chat-FF4081?style=flat-square&logo=webrtc" />
  <img src="https://img.shields.io/badge/yt--dlp-YouTube_Downloader-FF0000?style=flat-square&logo=youtube" />
  <img src="https://img.shields.io/badge/MongoDB-Database-47A248?style=flat-square&logo=mongodb" />
  <img src="https://img.shields.io/badge/FFmpeg-Media_Processing-007808?style=flat-square&logo=ffmpeg" />
  <img src="https://img.shields.io/badge/Heroku-Deployment-430098?style=flat-square&logo=heroku" />
</p>

| Technology | Purpose / কাজ |
|------------|----------------|
| **Pyrofork** (Pyrogram Fork) | Telegram MTProto client — বটের মূল ফ্রেমওয়ার্ক |
| **PyTgCalls** | Voice Chat streaming — ভয়েস চ্যাটে অডিও/ভিডিও স্ট্রিম |
| **yt-dlp** | YouTube search & download — ইউটিউব থেকে গান খোঁজা ও ডাউনলোড |
| **MongoDB (Motor)** | Async database — ইউজার ও গ্রুপের ডাটা সংরক্ষণ |
| **FFmpeg** | Audio/video processing — মিডিয়া প্রসেসিং |
| **aiohttp / aiofiles** | Async HTTP & file operations — দ্রুত নেটওয়ার্ক অপারেশন |

---

## 🚀 Deployment / ডিপ্লয়মেন্ট

### Prerequisites / পূর্বশর্ত

| Requirement | Source / উৎস |
|-------------|--------------|
| **API_ID** & **API_HASH** | [my.telegram.org](https://my.telegram.org) |
| **BOT_TOKEN** | [@BotFather](https://t.me/BotFather) |
| **STRING_SESSION** | Pyrogram v2 string session generator |
| **MONGO_DB_URI** | [MongoDB Atlas](https://www.mongodb.com/atlas) |
| **LOG_GROUP_ID** | Your Telegram log group ID |

### Option 1: Deploy to Heroku / হেরোকুতে ডিপ্লয়

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/RajSukh81/MusicBangla)

### Option 2: Local / VPS Setup / লোকাল সেটআপ

```bash
# Clone the repository / রেপো ক্লোন করো
git clone https://github.com/RajSukh81/MusicBangla.git
cd MusicBangla

# Install dependencies / ডিপেন্ডেন্সি ইনস্টল করো
pip install -r requirements.txt

# Set up environment variables / এনভায়রনমেন্ট ভেরিয়েবল সেট করো
# Create a .env file with your credentials
cp .env.example .env
nano .env

# Run the bot / বট চালাও
python3 -m MusicBangla
```

### Environment Variables / এনভায়রনমেন্ট ভেরিয়েবল

| Variable | Required | Description |
|----------|----------|-------------|
| `API_ID` | ✅ | Telegram API ID |
| `API_HASH` | ✅ | Telegram API Hash |
| `BOT_TOKEN` | ✅ | Bot token from BotFather |
| `STRING_SESSION` | ✅ | Pyrogram v2 string session |
| `MONGO_DB_URI` | ✅ | MongoDB connection URI |
| `OWNER_ID` | ✅ | Your Telegram user ID |
| `OWNER_USERNAME` | ✅ | Your Telegram username |
| `LOG_GROUP_ID` | ✅ | Log group chat ID |
| `SUPPORT_GROUP` | ❌ | Support group link |
| `SUPPORT_CHANNEL` | ❌ | Support channel link |

---

## 🎯 Highlights / বিশেষত্ব

<table>
<tr>
<td align="center" width="25%">
  <h3>🎶</h3>
  <b>HD Music</b><br/>
  <sub>YouTube থেকে হাই-কোয়ালিটি গান স্ট্রিম করো — সরাসরি ভয়েস চ্যাটে</sub><br/>
  <sub><i>Stream high-quality music from YouTube directly in Voice Chat</i></sub>
</td>
<td align="center" width="25%">
  <h3>🎮</h3>
  <b>9 Games</b><br/>
  <sub>Tic-Tac-Toe, Quiz, Truth/Dare, RPS সহ ৯টি ইন্টারেক্টিভ গেম</sub><br/>
  <sub><i>9 interactive games including TTT, Quiz, Truth/Dare & more</i></sub>
</td>
<td align="center" width="25%">
  <h3>👥</h3>
  <b>Smart Tag</b><br/>
  <sub>একটি কমান্ডেই সবাইকে মেনশন করো — ফ্লাড কন্ট্রোল সহ</sub><br/>
  <sub><i>Mention all members with a single command — with flood control</i></sub>
</td>
<td align="center" width="25%">
  <h3>🌸</h3>
  <b>Auto Welcome</b><br/>
  <sub>নতুন মেম্বারদের সুন্দরভাবে স্বাগত জানাও — ছবি ও স্টিকার সহ</sub><br/>
  <sub><i>Beautiful welcome messages for new members with photos & stickers</i></sub>
</td>
</tr>
</table>

---

## 🎲 Game Details / গেমের বিস্তারিত

<details>
<summary><b>⭕ Tic-Tac-Toe (দুইজনে খেলো)</b></summary>

> `/ttt` কমান্ড দিয়ে শুরু করো। দ্বিতীয় প্লেয়ার যেকোনো ঘরে ক্লিক করে জয়েন করবে। ইনলাইন বাটন দিয়ে খেলো — কে জিতবে? 🏆
>
> Start with `/ttt`. Second player joins by clicking any cell. Play via inline buttons — who wins?

</details>

<details>
<summary><b>🎯 Truth or Dare (সত্য অথবা সাহস)</b></summary>

> `/truth` — একটি র‍্যান্ডম সত্য প্রশ্ন পাও। `/dare` — একটি র‍্যান্ডম ডেয়ার চ্যালেঞ্জ পাও। `/td` — র‍্যান্ডমলি সত্য অথবা ডেয়ার পাও। সব বাংলায়!
>
> `/truth` for random truth, `/dare` for random dare, `/td` for either. All in Bangla!

</details>

<details>
<summary><b>✊ Rock Paper Scissors (পাথর কাগজ কাঁচি)</b></summary>

> `/rps` দিয়ে বটের সাথে খেলো! ইনলাইন বাটনে Rock, Paper বা Scissors সিলেক্ট করো — বট তোমার বিরুদ্ধে খেলবে। 🤖
>
> Play against the bot with `/rps`! Select your choice via inline buttons.

</details>

<details>
<summary><b>🧠 Quiz (বাংলা কুইজ)</b></summary>

> `/quiz` কমান্ড দিলে একটি বাংলা সাধারণ জ্ঞান প্রশ্ন আসবে — ৪টি অপশন থেকে সঠিক উত্তর বেছে নাও!
>
> Get a Bangla GK question with 4 options. Pick the right answer!

</details>

<details>
<summary><b>🔮 Magic 8-Ball & More (আরো গেম)</b></summary>

> - `/8ball <প্রশ্ন>` — ম্যাজিক ৮-বলকে যেকোনো প্রশ্ন জিজ্ঞেস করো / Ask the magic 8-ball anything
> - `/flip` — কয়েন ফ্লিপ (Heads or Tails) / Flip a coin
> - `/dice` — ডাইস রোল (1-6) / Roll a dice

</details>

---

## 🤝 Contributing / অবদান রাখুন

Contributions are welcome! Feel free to open issues and pull requests.

অবদান রাখতে চাইলে অবশ্যই স্বাগতম! Issue বা Pull Request খুলুন।

```bash
# Fork & clone / ফর্ক করে ক্লোন করো
git clone https://github.com/<your-username>/MusicBangla.git
cd MusicBangla

# Create a new branch / নতুন ব্রাঞ্চ তৈরি করো
git checkout -b feature/your-feature

# Make changes & commit / পরিবর্তন করো ও কমিট করো
git add .
git commit -m "Add your feature"

# Push & create PR / পুশ করে PR তৈরি করো
git push origin feature/your-feature
```

---

## 📬 Contact / যোগাযোগ

<p align="center">
  <a href="https://t.me/R4J_81"><img src="https://img.shields.io/badge/Telegram-@R4J__81-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram" /></a>
  <a href="https://github.com/RajSukh81"><img src="https://img.shields.io/badge/GitHub-RajSukh81-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub" /></a>
  <a href="https://t.me/RupkothaGolpo"><img src="https://img.shields.io/badge/Channel-RupkothaGolpo-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" alt="Channel" /></a>
</p>

---

## ⭐ Support / সমর্থন করুন

> এই প্রজেক্ট ভালো লাগলে একটা **⭐ Star** দিয়ে সমর্থন জানান!
>
> If you like this project, give it a **⭐ Star** to show your support!

<p align="center">
  <a href="https://github.com/RajSukh81/MusicBangla/stargazers">
    <img src="https://img.shields.io/github/stars/RajSukh81/MusicBangla?style=for-the-badge&color=yellow&logo=github" alt="Star this repo" />
  </a>
</p>

---

<p align="center">
  <b>Made with ❤️ by <a href="https://t.me/R4J_81">RajSukh81</a></b><br/>
  <sub>🇮🇳 ভারত থেকে ভালোবাসায় তৈরি | Built with love from India 🇮🇳</sub>
</p>
