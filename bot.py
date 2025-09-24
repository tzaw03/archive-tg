#!/usr/bin/env python3
"""
Archive.org to Telegram Channel Bot
Author: Your Name
Version: 1.0.0
Python 3.9+ compatible
"""

import os
import logging
import asyncio
from typing import Dict, Any
from datetime import datetime
import json

from telethon import TelegramClient, events, Button
from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeVideo
from telethon.errors import FloodWaitError, ChatWriteForbiddenError

from archive_handler import ArchiveOrgHandler
from telegram_handler import TelegramChannelHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
API_ID = int(os.environ.get('TELEGRAM_API_ID', '0'))
API_HASH = os.environ.get('TELEGRAM_API_HASH', '')
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHANNEL_ID = os.environ.get('TELEGRAM_CHANNEL_ID', '')
SESSION_NAME = os.environ.get('SESSION_NAME', 'archive_bot')

class ArchiveTelegramBot:
    def __init__(self):
        self.client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
        self.archive_handler = ArchiveOrgHandler()
        self.channel_handler = TelegramChannelHandler(self.client, CHANNEL_ID)
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
        
    async def start(self):
        """Bot ကို စတင်ပါ"""
        await self.client.start(bot_token=BOT_TOKEN)
        logger.info("Bot အောင်မြင်စွာ စတင်ပါသည်")
        
        # Event handlers တွေ ပြင်ဆင်ပါ
        self.client.add_event_handler(self.handle_download_command, events.NewMessage(pattern='/download'))
        self.client.add_event_handler(self.handle_callback, events.CallbackQuery)
        self.client.add_event_handler(self.handle_start, events.NewMessage(pattern='/start'))
        self.client.add_event_handler(self.handle_help, events.NewMessage(pattern='/help'))
        
        # Bot ကို အလုပ်လုပ်ပါ
        await self.client.run_until_disconnected()
    
    async def handle_start(self, event):
        """'/start' command ကို ကိုင်တွယ်ပါ"""
        welcome_text = """
🤖 **Archive.org to Telegram Bot**
        
I can download content from archive.org and upload it directly to your Telegram channel!

**Commands:**
• `/download [archive.org URL]` - Download and upload content
• `/help` - Show this help message

**Example:**
`/download https://archive.org/details/your-item`
        """
        await event.respond(welcome_text, parse_mode='markdown')
    
    async def handle_help(self, event):
        """'/help' command ကို ကိုင်တွယ်ပါ"""
        help_text = """
📋 **Help Guide**

**How to use:**
1. Send me an archive.org URL with /download command
2. I'll show you available formats (FLAC, MP3, WAV, etc.)
3. Choose your preferred format
4. I'll download and upload to the channel automatically

**Supported formats:**
• Audio: FLAC, MP3, WAV, OGG
• Video: MP4, MKV, AVI
• Images: JPG, PNG, GIF
• Documents: PDF, EPUB, TXT

**Features:**
• Direct streaming upload (no local storage)
• Progress tracking
• Automatic cleanup
• Support for large files (up to 2GB)
        """
        await event.respond(help_text, parse_mode='markdown')
    
    async def handle_download_command(self, event):
        """'/download' command ကို ကိုင်တွယ်ပါ"""
        user_id = event.sender_id
        message_text = event.message.text
        
        # URL ကို message ထဲကနေ ထုတ်ပါ
        try:
            url = message_text.split(' ', 1)[1].strip()
        except IndexError:
            await event.respond("❌ Please provide an archive.org URL\nExample: `/download https://archive.org/details/item-name`", parse_mode='markdown')
            return
        
        # Processing message ပြပါ
        processing_msg = await event.respond("🔍 Fetching archive.org metadata...")
        
        try:
            # archive.org ကနေ metadata ရယူပါ
            metadata = await self.archive_handler.get_metadata(url)
            
            if not metadata:
                await processing_msg.edit("❌ Unable to fetch metadata. Please check the URL.")
                return
            
            # Session data ကို သိမ်းပါ
            self.user_sessions[user_id] = {
                'url': url,
                'metadata': metadata,
                'message_id': processing_msg.id
            }
            
            # Available formats ရယူပါ
            formats = self.archive_handler.get_available_formats(metadata)
            
            if not formats:
                await processing_msg.edit("❌ No downloadable formats found.")
                return
            
            # Inline keyboard ဖန်တီးပါ
            buttons = []
            for format_name, files in formats.items():
                if files:  # Only show formats with files
                    count = len(files)
                    buttons.append([Button.inline(f"{format_name} ({count} files)", f"format_{format_name}")])
            
            if not buttons:
                await processing_msg.edit("❌ No downloadable formats available.")
                return
            
            # Cancel button ထည့်ပါ
            buttons.append([Button.inline("❌ Cancel", "cancel")])
            
            # Message ကို format selection နဲ့ ပြန်ပြပါ
            item_title = metadata.get('metadata', {}).get('title', 'Unknown Item')
            response_text = f"""
📁 **{item_title}**

Available formats:
Choose a format to download and upload to the channel:
            """
            
            await processing_msg.edit(response_text, buttons=buttons, parse_mode='markdown')
            
        except Exception as e:
            logger.error(f"Error processing download command: {e}")
            await processing_msg.edit(f"❌ Error: {str(e)}")
    
    async def handle_callback(self, event):
        """Inline keyboard callbacks ကို ကိုင်တွယ်ပါ"""
        user_id = event.sender_id
        data = event.data.decode('utf-8')
        
        # User မှာ active session ရှိမရှိ စစ်ဆေးပါ
        if user_id not in self.user_sessions:
            await event.answer("❌ Session expired. Please start over.", alert=True)
            return
        
        session = self.user_sessions[user_id]
        
        if data == 'cancel':
            del self.user_sessions[user_id]
            await event.edit("❌ Operation cancelled.")
            return
        
        if data.startswith('format_'):
            format_name = data.replace('format_', '', 1)
            
            try:
                # Selected format အတွက် files ရယူပါ
                formats = self.archive_handler.get_available_formats(session['metadata'])
                files = formats.get(format_name, [])
                
                if not files:
                    await event.answer("❌ No files available in this format.", alert=True)
                    return
                
                # Message ကို progress နဲ့ ပြန်ပြပါ
                await event.edit(f"📥 Downloading {format_name} format... Please wait.")
                
                # Files တွေ download နဲ့ upload လုပ်ပါ
                for i, file_info in enumerate(files):
                    file_name = file_info['name']
                    await event.edit(f"📥 Processing {file_name} ({i+1}/{len(files)})...")
                    
                    # File ကို download နဲ့ upload လုပ်ပါ
                    success = await self.download_and_upload_file(
                        file_info, session['metadata'], format_name
                    )
                    
                    if success:
                        await event.edit(f"✅ Uploaded: {file_name}")
                    else:
                        await event.edit(f"❌ Failed to upload: {file_name}")
                
                # Session ကို ရှင်းပါ
                del self.user_sessions[user_id]
                await event.edit("🎉 All files uploaded successfully!")
                
            except Exception as e:
                logger.error(f"Error processing format selection: {e}")
                await event.edit(f"❌ Error: {str(e)}")
                del self.user_sessions[user_id]
    
    async def download_and_upload_file(self, file_info: Dict[str, Any], metadata: Dict[str, Any], format_name: str) -> bool:
        """File ကို archive.org ကနေ download ပြီး Telegram channel ကို upload လုပ်ပါ"""
        try:
            # File stream ကို download ပါ
            file_stream = await self.archive_handler.download_file_stream(file_info)
            
            if not file_stream:
                return False
            
            # File metadata ရယူပါ
            file_name = file_info['name']
            file_size = file_info.get('size', 0)
            try:
                file_size = int(file_size)
            except (ValueError, TypeError):
                file_size = 0
            
            # Item metadata ကို caption နဲ့ embedding အတွက် ရယူပါ
            item_metadata = metadata.get('metadata', {})
            title = item_metadata.get('title', 'Unknown Title')
            creator = item_metadata.get('creator', 'Unknown Creator')
            date = item_metadata.get('date', 'Unknown Date')
            
            # Album art ကို metadata ကနေ ရှာပါ (ရှိရင်)
            album_art = None
            files = metadata.get('files', [])
            for f in files:
                try:
                    f_size = int(f.get('size', 0))
                except (ValueError, TypeError):
                    f_size = 0

                if f.get('name', '').lower().endswith(('.jpg', '.jpeg', '.png')) and f_size > 1024:
                    art_stream = await self.archive_handler.download_file_stream(f)
                    if art_stream:
                        album_art = art_stream.read()
                        break
            
            # Embedding အတွက် metadata ပြင်ဆင်ပါ
            embed_metadata = {
                "title": title,
                "creator": creator,
                "album": item_metadata.get('collection', 'Archive.org'),
                "album_art": album_art
            }
            
            # Caption ဖန်တီးပါ
            caption = f"""
📁 **{title}**
📅 {date}
💾 {format_name} format
📊 {self.format_file_size(file_size)}
            """.strip()
            
            # Channel ကို upload လုပ်ပါ (embedded metadata နဲ့)
            success = await self.channel_handler.upload_file(
                file_stream, file_name, caption, metadata=embed_metadata
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error downloading/uploading file: {e}")
            return False
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """File size ကို လူဖတ်လို့လွယ်တဲ့ format ပြင်ဆင်ပါ"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"

async def main():
    """Main function"""
    bot = ArchiveTelegramBot()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Bot ကို အသုံးပြုသူက ရပ်တန့်ပါသည်")
    except Exception as e:
        logger.error(f"Bot ပြသနာဖြစ်သွားပါသည်: {e}")

if __name__ == '__main__':
    asyncio.run(main())
