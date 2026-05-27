#!/bin/bash
# ============================================================
# MusicBangla Bot — VPS/Ubuntu Setup Script
# Oracle Cloud, Hetzner, Contabo, DigitalOcean, Linode, etc.
# ============================================================
# Usage: bash setup-vps.sh
# ============================================================

set -e

echo "=========================================="
echo "  MusicBangla Bot — VPS Setup"
echo "=========================================="

# --- Step 1: Install system dependencies ---
echo "[1/6] System dependencies install হচ্ছে..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv ffmpeg curl git

# --- Step 2: Install Node.js 22 (py-tgcalls এর জন্য) ---
echo "[2/6] Node.js install হচ্ছে..."
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash -
    sudo apt-get install -y nodejs
fi
echo "Node.js version: $(node -v)"

# --- Step 3: Clone repo ---
echo "[3/6] Repository clone হচ্ছে..."
if [ -d "MusicBangla" ]; then
    echo "MusicBangla folder exists, pulling latest..."
    cd MusicBangla && git pull && cd ..
else
    git clone https://github.com/RajSukh81/MusicBangla.git
fi
cd MusicBangla

# --- Step 4: Python virtual env + dependencies ---
echo "[4/6] Python dependencies install হচ্ছে..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# --- Step 5: Create .env file if not exists ---
echo "[5/6] .env ফাইল চেক হচ্ছে..."
if [ ! -f .env ]; then
    cat > .env << 'ENVEOF'
# === MusicBangla Bot Configuration ===
# সব value ডাবল কোটের মধ্যে দিন

API_ID=
API_HASH=
BOT_TOKEN=
MONGO_DB_URI=
OWNER_ID=
OWNER_USERNAME=
STRING_SESSION=
LOG_GROUP_ID=
SUPPORT_GROUP=
SUPPORT_CHANNEL=
YT_COOKIES=
ENVEOF
    echo ""
    echo "============================================"
    echo "  .env ফাইল তৈরি হয়েছে!"
    echo "  এখন .env ফাইলে সব value বসান:"
    echo "  nano .env"
    echo "============================================"
    echo ""
    exit 0
fi

# --- Step 6: Create systemd service ---
echo "[6/6] Systemd service তৈরি হচ্ছে..."
WORKDIR=$(pwd)
PYTHON_PATH="$WORKDIR/venv/bin/python3"

sudo tee /etc/systemd/system/musicbangla.service > /dev/null << EOF
[Unit]
Description=MusicBangla Telegram Music Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$WORKDIR
EnvironmentFile=$WORKDIR/.env
ExecStart=$PYTHON_PATH -m MusicBangla
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable musicbangla
sudo systemctl start musicbangla

echo ""
echo "=========================================="
echo "  MusicBangla Bot সফলভাবে চালু হয়েছে!"
echo "=========================================="
echo ""
echo "  দরকারী কমান্ড:"
echo "  sudo systemctl status musicbangla   — স্ট্যাটাস দেখুন"
echo "  sudo systemctl restart musicbangla  — রিস্টার্ট করুন"
echo "  sudo systemctl stop musicbangla     — বন্ধ করুন"
echo "  sudo journalctl -u musicbangla -f   — লাইভ লগ দেখুন"
echo ""
