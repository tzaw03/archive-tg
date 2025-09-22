# bot.py
#!/usr/bin/env python3
"""
Archive.org to Telegram Channel Bot
Author: Your Name
Version: 1.0.6
Python 3.9+ compatible
"""

import os
import logging
import asyncio
from typing import Dict, Any
import io
import base64

from telethon import TelegramClient, events, Button
from telethon.errors import FloodWaitError, ChatWriteForbiddenError

from archive_handler import ArchiveOrgHandler
from telegram_handler import TelegramChannelHandler

from mutagen.mp3 import MP3
from mutagen.id3 import ID3, ID3NoHeaderError, TIT2, TPE1, TALB, TDRC, TRCK, APIC
from mutagen.flac import FLAC, Picture
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE

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

# Channel ID must be integer, not string
CHANNEL_ID = int(os.environ.get('TELEGRAM_CHANNEL_ID', '0'))


class ArchiveTelegramBot:
    def __init__(self):
        self.client = TelegramClient("bot", API_ID, API_HASH)
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
            await event.respond(
                "❌ Please provide an archive.org URL\nExample: `/download https://archive.org/details/item-name`",
                parse_mode='markdown'
            )
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
        import os
        user_id = event.sender_id
        data = event.data.decode('utf-8')

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

                # --- Album-level metadata message ---
                item_metadata = session['metadata'].get('metadata', {})
                album_name = item_metadata.get('title', 'Unknown Album')
                release_date = item_metadata.get('date', 'Unknown Date')
                total_tracks = len(files)

                album_info = f"""
🎵 **Title:** {album_name}
📅 **Release Date:** {release_date}
🔢 **Total Tracks:** {total_tracks}
💽 **Format:** {format_name}
                """.strip()

                # Try to get album cover bytes (jpg/png)
                cover_bytes = None
                for f in session['metadata'].get('files', []):
                    name = f.get("name", "").lower()
                    if name.endswith((".jpg", ".jpeg", ".png")):
                        cover_stream = await self.archive_handler.download_file_stream(
                            {"identifier": self.archive_handler.current_identifier, "name": f["name"]}
                        )
                        if cover_stream:
                            try:
                                cover_stream.seek(0)
                                cover_bytes = cover_stream.read()
                            except Exception:
                                cover_bytes = None
                            finally:
                                try:
                                    cover_stream.close()
                                except Exception:
                                    pass
                        break

                # Send album cover with full metadata as caption (cover_bytes -> fresh BytesIO)
                if cover_bytes:
                    try:
                        album_cover_stream = io.BytesIO(cover_bytes)
                        album_cover_stream.seek(0)
                        await self.client.send_file(self.channel_handler.channel_id, album_cover_stream, caption=album_info)
                    finally:
                        try:
                            album_cover_stream.close()
                        except Exception:
                            pass
                else:
                    await self.channel_handler.send_message(album_info)

                # Now upload tracks one by one
                for i, file_info in enumerate(files):
                    file_name = file_info['name']
                    # use filename without extension as caption (no artist/provider)
                    track_title = os.path.splitext(file_name)[0]
                    track_caption = f"{track_title}"

                    await event.edit(f"📥 Uploading track {i+1}/{len(files)}: {track_title}")

                    file_stream = await self.archive_handler.download_file_stream(file_info)
                    if not file_stream:
                        await event.edit(f"❌ Failed to download: {track_title}")
                        continue

                    # Add metadata and album art to the file stream if it's an audio format
                    if format_name in ['FLAC', 'MP3', 'WAV', 'OGG']:
                        await self.add_metadata_to_audio(
                            file_stream,
                            file_info,
                            item_metadata,
                            cover_bytes,
                            str(i+1),
                            format_name
                        )

                    # Ensure pointer at start for the file to upload
                    try:
                        file_stream.seek(0)
                    except Exception:
                        pass

                    # Prepare a fresh thumb stream per upload (if we have cover bytes)
                    thumb_stream = None
                    if cover_bytes:
                        thumb_stream = io.BytesIO(cover_bytes)
                        try:
                            thumb_stream.seek(0)
                        except Exception:
                            pass

                    # Upload (telegram_handler.upload_file will also seek(0) defensively)
                    success = await self.channel_handler.upload_file(
                        file_stream,
                        file_name,
                        caption=track_caption,
                        thumb=thumb_stream
                    )

                    # Close streams after upload attempt
                    try:
                        file_stream.close()
                    except Exception:
                        pass
                    if thumb_stream:
                        try:
                            thumb_stream.close()
                        except Exception:
                            pass

                    if not success:
                        await event.edit(f"❌ Failed to upload: {track_title}")

                # Clean up session
                del self.user_sessions[user_id]
                await event.edit("🎉 Album upload finished!")

            except Exception as e:
                logger.error(f"Error processing format selection: {e}")
                await event.edit(f"❌ Error: {str(e)}")
                if user_id in self.user_sessions:
                    del self.user_sessions[user_id]

    async def add_metadata_to_audio(self, file_stream: io.BytesIO, file_info: Dict, item_metadata: Dict, cover_bytes: Optional[bytes], track_num: str, format_name: str):
        """Add metadata and embed album art to audio file stream in memory"""
        try:
            file_stream.seek(0)
            ext = format_name.lower()
            title = file_info.get('title', os.path.splitext(file_info['name'])[0])
            artist = file_info.get('creator', item_metadata.get('creator', 'Unknown Artist'))
            album = item_metadata.get('title', 'Unknown Album')
            year = item_metadata.get('year', item_metadata.get('date', ''))
            track = file_info.get('track', track_num)

            if ext == 'mp3':
                try:
                    audio = MP3(file_stream, ID3=ID3)
                except ID3NoHeaderError:
                    audio = MP3(file_stream)
                    audio.add_tags()
                audio['TIT2'] = TIT2(encoding=3, text=title)
                audio['TPE1'] = TPE1(encoding=3, text=artist)
                audio['TALB'] = TALB(encoding=3, text=album)
                audio['TDRC'] = TDRC(encoding=3, text=year)
                audio['TRCK'] = TRCK(encoding=3, text=track)
                if cover_bytes:
                    audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=cover_bytes))
                audio.save(file_stream)

            elif ext == 'flac':
                audio = FLAC(file_stream)
                audio['title'] = title
                audio['artist'] = artist
                audio['album'] = album
                audio['date'] = year
                audio['tracknumber'] = track
                if cover_bytes:
                    picture = Picture()
                    picture.data = cover_bytes
                    picture.type = 3
                    picture.mime = 'image/jpeg'
                    audio.add_picture(picture)
                audio.save(file_stream)

            elif ext == 'ogg':
                audio = OggVorbis(file_stream)
                audio['title'] = title
                audio['artist'] = artist
                audio['album'] = album
                audio['date'] = year
                audio['tracknumber'] = track
                if cover_bytes:
                    picture = Picture()
                    picture.data = cover_bytes
                    picture.type = 3
                    picture.mime = 'image/jpeg'
                    audio['metadata_block_picture'] = [base64.b64encode(picture.write()).decode('ascii')]
                audio.save(file_stream)

            elif ext == 'wav':
                audio = WAVE(file_stream)
                if 'INFO' not in audio:
                    audio.add_tags()
                audio.tags['INAM'] = title  # Title
                audio.tags['IART'] = artist  # Artist
                audio.tags['IPRD'] = album  # Album/Product
                audio.tags['ICRD'] = year  # Creation date
                audio.tags['IPRT'] = track  # Part/Track number
                # Note: WAV does not support embedded album art natively
                audio.save(file_stream)

            file_stream.seek(0)
            logger.info(f"Metadata added to {file_info['name']}")

        except Exception as e:
            logger.error(f"Failed to add metadata to {file_info.get('name', 'unknown')}: {e}")
            file_stream.seek(0)  # Reset stream even on error

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
