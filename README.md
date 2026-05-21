# 🎵 MusicBangla — Multi-Functional Telegram Music Bot

[**বাংলা সংস্করণ নিচে দেওয়া হয়েছে (Bengali version is below)**](#-বাংলা-সংস্করণ)

MusicBangla is a powerful, fast, and feature-rich Telegram bot designed to stream high-quality audio and video directly into group Voice Chats (VC) using **yt-dlp**. It bypasses YouTube's strict bot-detection mechanisms and also features interactive in-line games and smart user mention/tagging systems to keep your community active!

---

## ✨ Features

* 🎵 **Audio & Video Streaming:** Supports high-quality audio and video playback in Telegram Voice Chats.
* 🎮 **In-line Games:** Play fun text-based and interactive games directly within the group.
* 📣 **Mass Mention / TagAll:** Smart tool to tag or mention group members easily.
* 🚀 **Superfast Downloads:** Parallel downloading and efficient voice chat streaming handling.
* 🛡️ **YouTube Bypass:** Advanced custom user-agents and Netscape cookies support to avoid YouTube bot-detection and IP blocking.
* 📊 **API-Less Search:** No external YouTube Data API key or proxy required; search directly by name.

---

## 🛠️ Required Configuration (Config Vars)

Configure these environment variables in your Heroku or VPS dashboard:

| Key | Description | Example |
| :--- | :--- | :--- |
| `API_ID` | Your Telegram API ID (from my.telegram.org) | `1234567` |
| `API_HASH` | Your Telegram API Hash | `abcdef1234567890abcdef...` |
| `BOT_TOKEN` | Telegram Bot Token from @BotFather | `123456:ABC-DEF1234ghIkl-zyx` |
| `STRING_SESSION` | Pyrogram String Session of the Assistant Account | `BQAzA...` |
| `OWNER_USERNAME` | Username of the owner (without `@`) | `RajSukh81` |
| `LOG_GROUP_ID` | Bot Log Group ID (Must start with `-100`) | `-1003935489315` |
| `YT_COOKIES` | *(Optional)* Netscape format cookies text to bypass YouTube bot blocks | `### Netscape HTTP Cookie File...` |

---

## 🚀 Deployment Guide

### Deploying on Heroku:

1. **Connect Repository:** Go to your Heroku App -> 'Deploy' tab and connect your `RajSukh81/MusicBangla` repository.
2. **Setup Config Vars:** Go to 'Settings' -> Click **Reveal Config Vars** and add the keys and values from the table above.
3. **Add Buildpacks:** In the 'Settings' tab, ensure you have added these buildpacks:
   * `heroku/python`
   * `heroku/nodejs` (Required for py-tgcalls)
4. **Deploy Branch:** Go back to the 'Deploy' tab and click **Deploy Branch**.
5. **Turn on Dynos:** Once successfully built, go to 'Resources' and enable the `worker: python3 -m MusicBangla` dyno.

---

## 📜 Bot Commands

### 🎵 Music Commands:
* `/play <song name or link>` — Play audio in group Voice Chat.
* `/vplay <video name or link>` — Play video in group Voice Chat.
* `/pause` — Pause current playback.
* `/resume` — Resume paused playback.
* `/skip` — Skip current track.
* `/stop` — Stop streaming and clear VC.

### 🎮 Games & Utilities:
* `/game` or `/games` — Open interactive inline games menu.
* `/mention` or `/tagall` — Mention all active members of the group.

---

# 🇧🇩 বাংলা সংস্করণ

MusicBangla হলো একটি শক্তিশালী এবং দ্রুতগতির টেলিগ্রাম মিউজিক বট, যা কোনো থার্ড-পার্টি API বা প্রক্সি ছাড়াই সরাসরি **yt-dlp** এর মাধ্যমে টেলিগ্রাম গ্রুপ ভয়েস চ্যাটে (VC) গান এবং ভিডিও প্লে করতে পারে। এর পাশাপাশি গ্রুপ চ্যাট জমিয়ে রাখতে এতে যুক্ত করা হয়েছে **মজার গেম** এবং **মেম্বারদের ট্যাগ/মেনশন** করার মতো ফিচারসমূহ।

---

## ✨ বৈশিষ্ট্যসমূহ

* 🎵 **অডিও এবং ভিডিও স্ট্রিমিং:** ভয়েস চ্যাটে হাই-কোয়ালিটি মিউজিক এবং ভিডিও প্লেব্যাক সাপোর্ট।
* 🎮 **ইন-লাইন গেমস:** বটের মাধ্যমেই সরাসরি গ্রুপে বসে গেম খেলার সুবিধা।
* 📣 **নাম মেনশন ও ট্যাগিং:** গ্রুপের সকল মেম্বারদের একসাথে সুন্দরভাবে ট্যাগ বা মেনশন করার সিস্টেম।
* 🛡️ **ইউটিউব বাইপাস মেকানিজম:** ইউটিউব বট-ডিটেকশন এবং আইপি ব্লকিং এড়ানোর জন্য বিশেষ কুকিজ ও মোবাইল ক্লায়েন্ট সাপোর্ট।

---

## 🚀 ডেপ্লয় করার নিয়ম (Heroku)

1. **GitHub রিপোজিটরি লিংক করুন:** Heroku অ্যাপের 'Deploy' ট্যাবে গিয়ে আপনার `RajSukh81/MusicBangla` রিপোজিটরি কানেক্ট করুন।
2. **Config Vars সেট করুন:** 'Settings' ট্যাবে গিয়ে **Reveal Config Vars**-এ প্রয়োজনীয় সকল Key এবং Value (যেমন: API_ID, BOT_TOKEN ইত্যাদি) যুক্ত করুন।
3. **Buildpacks যুক্ত করুন:** আপনার অ্যাপের 'Settings'-এ নিচের বিল্ডপ্যাকগুলো অবশ্যই থাকতে হবে:
   * `heroku/python`
   * `heroku/nodejs`
4. **Deploy Branch:** এবার 'Deploy' ট্যাবে ফিরে গিয়ে **Deploy Branch** বাটনে ক্লিক করুন। 
5. **Dynos অন করুন:** ডেপ্লয় শেষ হলে 'Resources' ট্যাবে গিয়ে `worker` ডাইনোটি চালু (Turn on) করে দিন।

---

## 📜 বটের মূল কমান্ডসমূহ

* `/play <গানের নাম>` — গ্রুপ ভয়েস চ্যাটে অডিও গান বাজানোর জন্য।
* `/vplay <ভিডিওর নাম>` — ভিডিও সহ গান বাজানোর জন্য।
* `/pause` / `/resume` / `/skip` / `/stop` — মিউজিক কন্ট্রোল করার জন্য।
* `/game` — গ্রুপে গেম খেলার অপশন চালু করার জন্য।
* `/mention` — গ্রুপের মেম্বারদের ট্যাগ করার জন্য।

---

## 👨‍💻 Developer & Owner Contact

* **GitHub Profile:** [@RajSukh81](https://github.com/RajSukh81)
* **Telegram Support:** [Raj Sukh](https://t.me/R4J_81)
* 
