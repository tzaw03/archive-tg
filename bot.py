#!/usr/bin/env python3
"""
Archive.org to Telegram Channel Bot
Version: 2.0.0 (Myanmar Version)
Author: Archive Bot Team
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

# Logging setup
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
        self.session_timeout = 3600  # 60 မိနစ်
        
    async def start(self):
        """Bot ကိုစတင်ပါ"""
        await self.client.start(bot_token=BOT_TOKEN)
        logger.info("Bot စတင်ပြီးပါပြီ")
        
        # Event handlers တွေထည့်ပါ
        self.client.add_event_handler(self.handle_start, events.NewMessage(pattern='/start'))
        self.client.add_event_handler(self.handle_help, events.NewMessage(pattern='/help'))
        self.client.add_event_handler(self.handle_formats, events.NewMessage(pattern='/formats'))
        self.client.add_event_handler(self.handle_cancel, events.NewMessage(pattern='/cancel'))
        self.client.add_event_handler(self.handle_download_command, events.NewMessage(pattern='/download'))
        self.client.add_event_handler(self.handle_callback, events.CallbackQuery)
        
        # Bot ကိုအလုပ်လုပ်အောင်စောင့်ပါ
        await self.client.run_until_disconnected()
    
    async def handle_start(self, event):
        """/start command ကိုဖြေကြားပါ"""
        welcome_text = """
🤖 **Archive.org Music Downloader Bot**
        
🎵 **archive.org ကနေ သီချင်းတွေကို download လုပ်ပြီး channel ထဲကို upload ပေးနိုင်ပါတယ်**

**📝 အသုံးပြုနည်းများ:**
• `/download [archive.org URL]` - သီချင်းတွေ download လုပ်မယ်
• `/formats` - ထောက်ပံ့ပေးတဲ့ format တွေကြည့်မယ်  
• `/help` - အသေးစိတ်အကူအညီ
• `/cancel` - လုပ်ဆောင်ချက်ရပ်မယ်

**🎯 အလွယ်ကူဆုံး:**
`/download https://archive.org/details/your-album`

**⏰ Session Timeout:** 30 မိနစ်
        """
        await event.respond(welcome_text, parse_mode='markdown')
    
    async def handle_help(self, event):
        """/help command ကိုဖြေကြားပါ"""
        help_text = """
📋 **အကူအညီလိုအပ်ပါသလား**

**🎵 ထောက်ပံ့ပေးတဲ့ Audio Format တွေ:**
• FLAC (အရည်အသွေးအကောင်းဆုံး)
• WAV ( uncompressed )
• MP3 (compressed)
• OGG (open format)

**📁 အခြား File တွေ:**
• Album Art (JPG/PNG)
• Torrent files
• PDF booklets

**🚀 အသုံးပြုနည်း:**

၁။ **archive.org မှာ သီချင်းရှာပါ**
၂။ **URL ကို copy လုပ်ပါ** (ဥပမာ: https://archive.org/details/gratefuldead)
၃။ **Command ပို့ပါ:** `/download [URL]`
၄။ **Format ရွေးပါ** button တွေကနေ
၅။ **Upload ပြီးတော့စောင့်ပါ**

**⚡ အကြံပြုချက်များ:**
• FLAC ကိုအရည်အသွအကောင်းဆုံးအတွက်သုံးပါ
• MP3 ကို file size သေးချင်တဲ့အခါသုံးပါ
• JPG ကို album cover အတွက်သုံးပါ

**❓ အကူအညီလိုပါသလား?**
Contact: @rgraves
        """
        await event.respond(help_text, parse_mode='markdown')

    async def handle_formats(self, event):
        """/formats command ကိုဖြေကြားပါ"""
        formats_text = """
🎵 **ထောက်ပံ့ပေးတဲ့ Format တွေ:**

**🔊 Lossless (အရည်အသွေးအကောင်းဆုံး):**
• FLAC - Free Lossless Audio Codec
• WAV - Uncompressed Wave

**🎧 Compressed (အရည်အသွကောင်းသည်):**
• MP3 - MPEG Audio Layer 3
• OGG - Ogg Vorbis

**📷 အခြား File တွေ:**
• JPG/PNG - Album artwork
• PDF - Digital booklets
• TORRENT - Torrent files

**💡 အရည်အသွေးမှတ်ချက်:**
• FLAC = CD quality (file ကြီးသည်)
• MP3 320kbps = High quality
• OGG = Open source alternative

**📊 File Size:**
• FLAC: 30-50MB တစ်ပုဒ်စီ
• MP3: 3-10MB တစ်ပုဒ်စီ
• WAV: 50-80MB တစ်ပုဒ်စီ
        """
        await event.respond(formats_text, parse_mode='markdown')

    async def handle_cancel(self, event):
        """/cancel command ကိုဖြေကြားပါ"""
        user_id = event.sender_id
        
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
            await event.respond("✅ **လုပ်ဆောင်ချက်ကို ရပ်ဆိုင်းလိုက်ပါပြီ**\n\n`/download` နဲ့ download အသစ်စတင်နိုင်ပါသည်။", parse_mode='markdown')
        else:
            await event.respond("ℹ️ **ရပ်ဆိုင်းစရာ လုပ်ဆောင်ချက်မရှိပါ**\n\n`/download` နဲ့ download စတင်နိုင်ပါသည်။", parse_mode='markdown')

    async def handle_download_command(self, event):
        """/download command ကိုဖြေကြားပါ"""
        user_id = event.sender_id
        
        # Session ရှိမရှိစစ်ပါ
        if user_id in self.user_sessions:
            await event.respond("⚠️ သင့်မှာ active download session ရှိပါသည်။ `/cancel` နဲ့ စ重新开始 လုပ်နိုင်ပါသည်။")
            return
        
        message_text = event.message.text
        
        # URL ကို extract လုပ်ပါ
        try:
            url = message_text.split(' ', 1)[1].strip()
        except IndexError:
            await event.respond("❌ **archive.org URL ကို ထည့်ပေးပါ**\n\n**ဥပမာ:**\n`/download https://archive.org/details/gratefuldead-sbd`", parse_mode='markdown')
            return
        
        # URL ကို validate လုပ်ပါ
        if not url.startswith(('http://archive.org', 'https://archive.org')):
            await event.respond("❌ **URL မမှန်ပါ**\narchive.org URL ဖြစ်ရမည်")
            return
        
        # Processing message ကိုပြပါ
        processing_msg = await event.respond("🔍 **archive.org metadata ကို ရယူနေပါသည်...**\n⏱️ အချိန်အနည်းငယ်စောင့်ပါ...")
        
        try:
            # archive.org ကနေ metadata ရယူပါ
            metadata = await self.archive_handler.get_metadata(url)
            
            if not metadata:
                await processing_msg.edit("❌ **Metadata ရယူနိုင်မည်မဟုတ်ပါ**\nURL ကိုစစ်ပြီးပြန်ကြိုးစားပါ။")
                return
            
            # Session data သိမ်းပါ
            self.user_sessions[user_id] = {
                'url': url,
                'metadata': metadata,
                'message_id': processing_msg.id,
                'timestamp': datetime.now()
            }
            
            # Available formats ရယူပါ
            formats = self.archive_handler.get_available_formats(metadata)
            
            if not formats:
                await processing_msg.edit("❌ **Download လုပ်နိုင်သော format မရှိပါ**\nဒီ item မှာ audio files မရှိနိုင်ပါ။")
                return
            
            # Format selection message ဖန်တီးပါ
            item_title = metadata.get('metadata', {}).get('title', 'Unknown Item')
            item_creator = metadata.get('metadata', {}).get('creator', 'Unknown Artist')
            
            response_text = f"""
🎵 **{item_title}**
👤 **{item_creator}**

📊 **ရရှိနိုင်သော Format တွေ:**
            """
            
            # Inline keyboard ဖန်တီးပါ
            buttons = []
            for format_name, files in formats.items():
                if files:
                    file_count = len(files)
                    total_size = sum(int(f.get('size', 0)) for f in files)
                    size_str = self.format_file_size(total_size)
                    buttons.append([Button.inline(f"🎵 {format_name} ({file_count} files, {size_str})", f"format_{format_name}")])
            
            if not buttons:
                await processing_msg.edit("❌ **Download လုပ်နိုင်သော format မရှိပါ**")
                return
            
            # Utility buttons ထည့်ပါ
            buttons.append([
                Button.inline("🔄 Refresh", "refresh"),
                Button.inline("❌ Cancel", "cancel")
            ])
            
            # Message ကို update လုပ်ပါ
            await processing_msg.edit(response_text, buttons=buttons, parse_mode='markdown')
            
        except Exception as e:
            logger.error(f"Download command error: {e}")
            await processing_msg.edit(f"❌ **Error:** {str(e)}\nကြိုးစားပြီးမရရင် support ကိုဆက်သွယ်ပါ။")
            
            # Error တက်ရင် session သန့်ရှင်းပါ
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]

    async def handle_callback(self, event):
        """Callback queries ကိုဖြေကြားပါ"""
        user_id = event.sender_id
        data = event.data.decode('utf-8')
        
        # Session ရှိမရှိစစ်ပါ
        if user_id not in self.user_sessions:
            await event.answer("❌ Session ပျက်သွားပါပြီ။ `/download` နဲ့ စ重新开始 လုပ်ပါ။", alert=True)
            return
        
        # Session timeout စစ်ပါ
        session = self.user_sessions[user_id]
        if (datetime.now() - session.get('timestamp', datetime.now())).seconds > self.session_timeout:
            del self.user_sessions[user_id]
            await event.answer("⏰ Session time out ဖြစ်သွားပါပြီ။ `/download` နဲ့ စ重新开始 လုပ်ပါ။", alert=True)
            return
        
        if data == 'cancel':
            del self.user_sessions[user_id]
            await event.edit("❌ **Download ရပ်ဆိုင်းလိုက်ပါပြီ**\n\n`/download` နဲ့ download အသစ်စတင်နိုင်ပါသည်။", parse_mode='markdown')
            return
        
        if data == 'refresh':
            await event.answer("🔄 Refreshing...", alert=False)
            # Metadata ပြန်ရယူပါ
            try:
                metadata = await self.archive_handler.get_metadata(session['url'])
                if metadata:
                    session['metadata'] = metadata
                    await event.answer("✅ Successfully refreshed!", alert=False)
                else:
                    await event.answer("❌ Failed to refresh", alert=True)
            except:
                await event.answer("❌ Refresh failed", alert=True)
            return
        
        if data.startswith('format_'):
            format_name = data.replace('format_', '', 1)
            
            try:
                # Selected format အတွက် files ရယူပါ
                formats = self.archive_handler.get_available_formats(session['metadata'])
                files = formats.get(format_name, [])
                
                if not files:
                    await event.answer("❤️ ဒီ format မှာ files မရှိပါ", alert=True)
                    return
                
                # Progress ပြပါ
                await event.edit(f"📥 **{format_name} download ပြင်ဆင်နေပါသည်...**\n\n⏳ ကြီးမားသော files တွေအတွက် မိနစ်အနည်းငယ်စောင့်ပါ။")
                
                # Files တွေကို upload လုပ်ပါ
                uploaded_count = 0
                total_count = len(files)
                
                for i, file_info in enumerate(files):
                    file_name = file_info['name']
                    file_size = int(file_info.get('size', 0))
                    
                    # Progress update
                    progress_text = f"📥 **{format_name} downloading**\n\n📄 File {i+1}/{total_count}\n📊 {file_name}\n💾 {self.format_file_size(file_size)}"
                    await event.edit(progress_text)
                    
                    # Download and upload
                    success = await self.download_and_upload_file(
                        file_info, session['metadata'], format_name
                    )
                    
                    if success:
                        uploaded_count += 1
                        await event.edit(f"✅ **Uploaded:** {file_name}\n\n📊 Progress: {uploaded_count}/{total_count}")
                    else:
                        await event.edit(f"❌ **Failed:** {file_name}\n\n📊 Progress: {uploaded_count}/{total_count}")
                
                # Final message
                if uploaded_count == total_count:
                    await event.edit(f"🎉 **{format_name} files အားလုံး upload ပြီးပါပြီ!**\n\n📊 Total: {uploaded_count} files\n\n💡 `/download` နဲ့ download အသစ်စတင်နိုင်ပါသည်။")
                else:
                    await event.edit(f"⚠️ **Partial upload ပြီးပါပြီ**\n\n✅ Success: {uploaded_count}/{total_count}\n\n💡 `/download` နဲ့ ပြန်ကြိုးစားနိုင်ပါသည်။")
                
                # Session သန့်ရှင်းပါ
                del self.user_sessions[user_id]
                
            except Exception as e:
                logger.error(f"Format selection error: {e}")
                await event.edit(f"❌ **Upload failed:** {str(e)}\n\n💡 `/download` နဲ့ ပြန်ကြိုးစားပါ။")
                del self.user_sessions[user_id]

    async def download_and_upload_file(self, file_info: Dict[str, Any], metadata: Dict[str, Any], format_name: str) -> bool:
        """archive.org ကနေ file download လုပ်ပြီး Telegram channel ထဲ upload လုပ်ပါ"""
        try:
            # File stream download လုပ်ပါ
            file_stream = await self.archive_handler.download_file_stream(file_info)
            
            if not file_stream:
                return False
            
            # File metadata ရယူပါ
            file_name = file_info['name']
            file_size = file_info.get('size', 0)
            
            # Item metadata ရယူပါ
            item_metadata = metadata.get('metadata', {})
            title = item_metadata.get('title', 'Unknown Title')
            creator = item_metadata.get('creator', 'Unknown Artist')
            date = item_metadata.get('date', 'Unknown Date')
            
            # Caption ဖန်တီးပါ
            caption = f"""
📁 **{title}**
👤 {creator}
📅 {date}
💾 {format_name} format
📊 {self.format_file_size(file_size)}
            """.strip()
            
            # Channel ထဲ upload လုပ်ပါ
            success = await self.channel_handler.upload_file(
                file_stream, file_name, caption
            )
            
            return success
            
        except Exception as e:
            logger.error(f"File download/upload error: {e}")
            return False
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """File size """
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
        logger.info("Bot ")
    except Exception as e:
        logger.error(f"Bot crash : {e}")

if __name__ == '__main__':
    asyncio.run(main())
