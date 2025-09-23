#!/usr/bin/env python3
"""
Archive.org to Telegram Channel Bot
Version: 2.0.0
"""
import os
import logging
import asyncio
from typing import Dict, Any
import io

from telethon import TelegramClient, events, Button
from archive_handler import ArchiveOrgHandler
from telegram_handler import TelegramChannelHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_ID = int(os.environ.get('TELEGRAM_API_ID', '0'))
API_HASH = os.environ.get('TELEGRAM_API_HASH', '')
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHANNEL_ID = os.environ.get('TELEGRAM_CHANNEL_ID', '')
SESSION_NAME = 'archive_bot'

class ArchiveTelegramBot:
    def __init__(self):
        self.client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
        self.archive_handler = ArchiveOrgHandler()
        try:
            self.channel_id_int = int(CHANNEL_ID)
        except ValueError:
            self.channel_id_int = CHANNEL_ID
        self.channel_handler = TelegramChannelHandler(self.client, self.channel_id_int)
        self.user_sessions: Dict[int, Dict[str, Any]] = {}

    async def start(self):
        await self.client.start(bot_token=BOT_TOKEN)
        logger.info("Bot started successfully")
        self.client.add_event_handler(self.handle_start_help, events.NewMessage(pattern='/start|/help'))
        self.client.add_event_handler(self.handle_download_command, events.NewMessage(pattern='/download'))
        self.client.add_event_handler(self.handle_callback, events.CallbackQuery)
        await self.client.run_until_disconnected()

    async def handle_start_help(self, event):
        await event.respond("Welcome! Use /download [archive.org URL] to start.", parse_mode='markdown')

    async def handle_download_command(self, event):
        user_id = event.sender_id
        try:
            url = event.message.text.split(' ', 1)[1].strip()
        except IndexError:
            await event.respond("Please provide an archive.org URL.", parse_mode='markdown')
            return
        
        processing_msg = await event.respond("Fetching metadata...")
        metadata = await self.archive_handler.get_metadata(url)
        if not metadata:
            await processing_msg.edit("Could not fetch metadata.")
            return

        self.user_sessions[user_id] = {'metadata': metadata}
        formats = self.archive_handler.get_available_formats(metadata)
        if not formats:
            await processing_msg.edit("No downloadable audio formats found.")
            return

        buttons = [Button.inline(f"{name} ({len(files)} files)", f"format_{name}") for name, files in formats.items()]
        keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        keyboard.append([Button.inline("Cancel", "cancel")])
        item_title = metadata.get('metadata', {}).get('title', 'Unknown')
        await processing_msg.edit(f"**{item_title}**\n\nSelect a format:", buttons=keyboard, parse_mode='markdown')

    async def handle_callback(self, event):
        user_id = event.sender_id
        data = event.data.decode('utf-8')
        session = self.user_sessions.get(user_id)
        if not session:
            await event.answer("Session expired.", alert=True)
            return

        if data == 'cancel':
            del self.user_sessions[user_id]
            await event.edit("Operation cancelled.")
            return

        if data.startswith('format_'):
            format_name = data.replace('format_', '')
            await event.edit(f"Format '{format_name}' selected. Starting...")
            asyncio.create_task(self.process_album_download(event, user_id, format_name))

    async def process_album_download(self, event, user_id: int, format_name: str):
        session = self.user_sessions[user_id]
        metadata = session['metadata']
        formats = self.archive_handler.get_available_formats(metadata)
        files_to_process = formats.get(format_name, [])

        try:
            status_msg = await self.client.send_message(user_id, "Downloading album art...")
            art_stream = await self.archive_handler.get_album_art_stream(metadata)

            album_meta = metadata.get('metadata', {})
            album_title = album_meta.get('title', 'Unknown Album')
            album_year = album_meta.get('date', album_meta.get('year', ''))
            
            caption = f"**Album:** {album_title}\n**Year:** {album_year}\n**Format:** {format_name}"
            if art_stream:
                await self.client.send_file(self.channel_id_int, file=art_stream, caption=caption, parse_mode='markdown')
                art_stream.seek(0)
            else:
                await self.client.send_message(self.channel_id_int, caption, parse_mode='markdown')

            total_files = len(files_to_process)
            for i, file_info in enumerate(files_to_process):
                file_name = file_info['name']
                identifier = file_info['identifier']
                await status_msg.edit(f"Downloading track {i+1}/{total_files}: {file_name}")
                original_audio_stream = await self.archive_handler.download_file_stream(identifier, file_name)
                if not original_audio_stream: continue

                track_meta = {
                    'title': os.path.splitext(file_name)[0],
                    'artist': album_meta.get('creator', 'Unknown Artist'),
                    'album': album_title,
                    'date': album_year
                }
                await status_msg.edit(f"Embedding metadata for: {file_name}")
                processed_audio_stream = self.channel_handler.embed_metadata(
                    original_audio_stream, file_name, track_meta, art_stream
                )
                
                await status_msg.edit(f"Uploading track {i+1}/{total_files}: {file_name}")
                track_caption = f"Track: {track_meta['title']}"
                await self.channel_handler.upload_file(
                    processed_audio_stream, file_name, track_caption, track_meta
                )

            await status_msg.edit(f"Process Complete! All {total_files} tracks uploaded.")
        except Exception as e:
            logger.error(f"Error during processing: {e}", exc_info=True)
            await self.client.send_message(user_id, f"A critical error occurred: {e}")
        finally:
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]

async def main():
    bot = ArchiveTelegramBot()
    try:
        await bot.start()
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)

if __name__ == '__main__':
    asyncio.run(main())
