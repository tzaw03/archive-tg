# Archive.org to Telegram Channel Bot

A sophisticated Telegram bot that downloads content from archive.org and uploads it directly to your Telegram channel with support for multiple formats and streaming uploads.

## Features

✅ **Multi-format Support**: FLAC, MP3, WAV, MP4, PDF, EPUB, and more  
✅ **Streaming Upload**: No local storage required  
✅ **Progress Tracking**: Real-time upload progress  
✅ **Large Files**: Support for files up to 2GB  
✅ **Railway.app Ready**: Optimized for Railway deployment  
✅ **Error Handling**: Comprehensive error handling and retry logic  
✅ **User-friendly**: Inline keyboard interface  

## Setup Instructions

### 1. Telegram Bot Setup

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Create a new bot with `/newbot`
3. Save your bot token
4. Get your API ID and Hash from [my.telegram.org](https://my.telegram.org)

### 2. Local Development

```bash
# Clone the repository
git clone https://github.com/yourusername/archive-telegram-bot.git
cd archive-telegram-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your credentials

# Run the bot
python bot.py
