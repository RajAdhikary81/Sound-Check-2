FROM python:3.12-slim

# Install system dependencies (ffmpeg + Node.js for py-tgcalls)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    gcc \
    g++ \
    make \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY . .

# Create downloads directory
RUN mkdir -p downloads

CMD ["python3", "-m", "MusicBangla"]
