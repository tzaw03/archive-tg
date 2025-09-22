# bot.py
#!/usr/bin/env python3
"""
Archive.org to Telegram Channel Bot
Author: Your Name
Version: 1.0.7
Python 3.9+ compatible
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional
import io

from telethon import TelegramClient, events, Button
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

                # --- Album-level metadata ---
                item_metadata = session['metadata'].get('metadata', {})
                album_name = item_metadata.get('title', 'Unknown Album')
                artist = item_metadata.get('creator', 'Unknown Artist')
                release_date = item_metadata.get('date', 'Unknown Date')
                total_tracks = len(files)

                album_info = f"""
🎵 **Title:** {album_name}
👤 **Artist:** {artist}
📅 **Release Date:** {release_date}
🔢 **Total Tracks:** {total_tracks}
💽 **Format:** {format_name}
                """.strip()

                # Try to get album cover bytes (prefer jpg/png from files)
                cover_bytes = None
                for f in session['metadata'].get('files', []):
                    name = f.get("name", "").lower()
                    if any(ext in name for ext in (".jpg", ".jpeg", ".png", ".gif")):
                        cover_info = {"identifier": self.archive_handler.current_identifier, "name": f["name"]}
                        cover_stream = await self.archive_handler.download_file_stream(cover_info)
                        if cover_stream:
                            try:
                                cover_stream.seek(0)
                                cover_bytes = cover_stream.read()
                                logger.info(f"Found album cover: {f['name']}")
                                break
                            except Exception as e:
                                logger.error(f"Error reading cover: {e}")
                            finally:
                                try:
                                    cover_stream.close()
                                except:
                                    pass

                # Send album cover with metadata if available, else text message
                if cover_bytes:
                    try:
                        album_cover_stream = io.BytesIO(cover_bytes)
                        album_cover_stream.name = "album_art.jpg"  # Set a name for Telegram
                        await self.client.send_file(CHANNEL_ID, album_cover_stream, caption=album_info)
                        logger.info("Album cover uploaded")
                    except Exception as e:
                        logger.error(f"Failed to upload album cover: {e}")
                        await self.channel_handler.send_message(album_info)
                    finally:
                        try:
                            album_cover_stream.close()
                        except:
                            pass
                else:
                    await self.channel_handler.send_message(album_info)

                # Upload tracks one by one with thumb (album art) and caption
                for i, file_info in enumerate(files, 1):
                    file_name = file_info['name']
                    base_name = os.path.splitext(os.path.basename(file_name))[0]
                    # Simple caption: artist - track title (from filename)
                    track_title = base_name.replace(f"{i:02d}. ", "").strip()  # Remove track number if present
                    track_caption = f"{artist} - {track_title}"

                    await event.edit(f"📥 Uploading track {i}/{total_tracks}: {track_title}")

                    file_stream = await self.archive_handler.download_file_stream(file_info)
                    if not file_stream:
                        await event.edit(f"❌ Failed to download: {track_title}")
                        continue

                    # Reset stream position
                    file_stream.seek(0)

                    # Prepare thumb stream (reuse cover_bytes)
                    thumb_stream = None
                    if cover_bytes:
                        thumb_stream = io.BytesIO(cover_bytes)
                        thumb_stream.seek(0)

                    # Upload with thumb and caption
                    success = await self.channel_handler.upload_file(
                        file_stream,
                        file_name,
                        caption=track_caption,
                        thumb=thumb_stream
                    )

                    # Cleanup
                    try:
                        file_stream.close()
                    except:
                        pass
                    if thumb_stream:
                        try:
                            thumb_stream.close()
                        except:
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
