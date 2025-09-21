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
from typing import Optional, Dict, Any
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
        """Start the bot"""
        await self.client.start(bot_token=BOT_TOKEN)
        logger.info("Bot started successfully")
        
        # Set up event handlers
        self.client.add_event_handler(self.handle_download_command, events.NewMessage(pattern='/download'))
        self.client.add_event_handler(self.handle_callback, events.CallbackQuery)
        self.client.add_event_handler(self.handle_start, events.NewMessage(pattern='/start'))
        self.client.add_event_handler(self.handle_help, events.NewMessage(pattern='/help'))
        
        # Run the bot
        await self.client.run_until_disconnected()
    
    async def handle_start(self, event):
        """Handle /start command"""
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
        """Handle /help command"""
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
        """Handle /download command"""
        user_id = event.sender_id
        message_text = event.message.text
        
        # Extract URL from message
        try:
            url = message_text.split(' ', 1)[1].strip()
        except IndexError:
            await event.respond("❌ Please provide an archive.org URL\nExample: `/download https://archive.org/details/item-name`", parse_mode='markdown')
            return
        
        # Show processing message
        processing_msg = await event.respond("🔍 Fetching archive.org metadata...")
        
        try:
            # Get metadata from archive.org
            metadata = await self.archive_handler.get_metadata(url)
            
            if not metadata:
                await processing_msg.edit("❌ Unable to fetch metadata. Please check the URL.")
                return
            
            # Store session data
            self.user_sessions[user_id] = {
                'url': url,
                'metadata': metadata,
                'message_id': processing_msg.id
            }
            
            # Get available formats
            formats = self.archive_handler.get_available_formats(metadata)
            
            if not formats:
                await processing_msg.edit("❌ No downloadable formats found.")
                return
            
            # Create inline keyboard
            buttons = []
            for format_name, files in formats.items():
                if files:  # Only show formats with files
                    count = len(files)
                    buttons.append([Button.inline(f"{format_name} ({count} files)", f"format_{format_name}")])
            
            if not buttons:
                await processing_msg.edit("❌ No downloadable formats available.")
                return
            
            # Add cancel button
            buttons.append([Button.inline("❌ Cancel", "cancel")])
            
            # Update message with format selection
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
        """Handle inline keyboard callbacks"""
        user_id = event.sender_id
        data = event.data.decode('utf-8')
        
        # Check if user has an active session
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
                # Get files for selected format
                formats = self.archive_handler.get_available_formats(session['metadata'])
                files = formats.get(format_name, [])
                
                if not files:
                    await event.answer("❌ No files available in this format.", alert=True)
                    return
                
                # Update message to show progress
                await event.edit(f"📥 Downloading {format_name} format... Please wait.")
                
                # Download and upload files
                for i, file_info in enumerate(files):
                    file_name = file_info['name']
                    await event.edit(f"📥 Processing {file_name} ({i+1}/{len(files)})...")
                    
                    # Download file directly to Telegram
                    success = await self.download_and_upload_file(
                        file_info, session['metadata'], format_name
                    )
                    
                    if success:
                        await event.edit(f"✅ Uploaded: {file_name}")
                    else:
                        await event.edit(f"❌ Failed to upload: {file_name}")
                
                # Clean up session
                del self.user_sessions[user_id]
                await event.edit("🎉 All files uploaded successfully!")
                
            except Exception as e:
                logger.error(f"Error processing format selection: {e}")
                await event.edit(f"❌ Error: {str(e)}")
                del self.user_sessions[user_id]
    
    async def download_and_upload_file(self, file_info: Dict[str, Any], metadata: Dict[str, Any], format_name: str) -> bool:
        """Download file from archive.org and upload to Telegram channel"""
        try:
            # Download file stream
            file_stream = await self.archive_handler.download_file_stream(file_info)
            
            if not file_stream:
                return False
            
            # Get file metadata
            file_name = file_info['name']
            file_size = file_info.get('size', 0)
            
            # Get item metadata for caption
            item_metadata = metadata.get('metadata', {})
            title = item_metadata.get('title', 'Unknown Title')
            creator = item_metadata.get('creator', 'Unknown Creator')
            date = item_metadata.get('date', 'Unknown Date')
            
            # Create caption
            caption = f"""
📁 **{title}**
👤 {creator}
📅 {date}
💾 {format_name} format
📊 {self.format_file_size(file_size)}
            """.strip()
            
            # Upload to channel
            success = await self.channel_handler.upload_file(
                file_stream, file_name, caption
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error downloading/uploading file: {e}")
            return False
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human readable format"""
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
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")

if __name__ == '__main__':
    asyncio.run(main())
