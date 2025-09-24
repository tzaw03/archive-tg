#!/usr/bin/env python3
"""
Telegram Channel Handler Module using Pyrogram
Handles all Telegram channel operations
"""

import asyncio
import logging
from typing import Optional, IO
from io import BytesIO
import mutagen
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB
from pyrogram import Client
from pyrogram.errors import FloodWait, ChatWriteForbidden
from pyrogram.types import InputMediaDocument

logger = logging.getLogger(__name__)

class TelegramChannelHandler:
    def __init__(self, api_id: str, api_hash: str, bot_token: str, channel_id: str):
        self.client = Client("bot_session", api_id=api_id, api_hash=api_hash, bot_token=bot_token)
        self.channel_id = channel_id  # Store as string (e.g., "-1003031099376")
        self.client.start()

    async def upload_file(self, file_stream: BytesIO, file_name: str, caption: str, metadata: dict = None) -> bool:
        """Upload file to Telegram channel with embedded metadata"""
        try:
            # Ensure channel_id starts with "-100" for private channels
            if not self.channel_id.startswith('-100'):
                logger.error(f"Invalid channel ID format: {self.channel_id}. Expected format: '-100xxxxxxx'.")
                return False

            # Use channel_id as is (Pyrogram handles it correctly)
            logger.info(f"Uploading {file_name} to channel {self.channel_id}...")
            file_stream.seek(0)

            # Embed metadata using Mutagen
            if file_name.lower().endswith(('.mp3', '.flac')) and metadata:
                temp_file = BytesIO(file_stream.read())
                temp_file.seek(0)

                if file_name.lower().endswith('.flac'):
                    try:
                        audio = FLAC(temp_file)
                        if audio:
                            if metadata.get("title"):
                                audio["title"] = metadata["title"]
                            if metadata.get("creator"):
                                audio["artist"] = metadata["creator"]
                            if metadata.get("album"):
                                audio["album"] = metadata["album"]
                            if "album_art" in metadata and metadata["album_art"]:
                                pic = Picture()
                                pic.data = metadata["album_art"]
                                pic.type = 3  # Cover (front)
                                pic.mime = 'image/jpeg' if metadata["album_art"][:2] != b'\x89PNG' else 'image/png'
                                audio.add_picture(pic)
                            audio.save(temp_file)
                            logger.info("FLAC metadata embedded successfully")
                    except Exception as e:
                        logger.warning(f"Mutagen error for FLAC {file_name}: {e}. Sending original file.")
                        temp_file.seek(0)

                elif file_name.lower().endswith('.mp3'):
                    try:
                        id3 = ID3(temp_file)
                    except mutagen.id3.ID3NoHeaderError:
                        id3 = ID3()
                    except Exception as e:
                        logger.warning(f"Mutagen error for MP3 {file_name}: {e}. Sending original file.")
                        id3 = None

                    if id3 is not None:
                        if metadata.get("title"):
                            id3.add(TIT2(encoding=3, text=metadata["title"]))
                        if metadata.get("creator"):
                            id3.add(TPE1(encoding=3, text=metadata["creator"]))
                        if metadata.get("album"):
                            id3.add(TALB(encoding=3, text=metadata["album"]))
                        if "album_art" in metadata and metadata["album_art"]:
                            mime = 'image/jpeg' if metadata["album_art"][:2] != b'\x89PNG' else 'image/png'
                            id3.add(APIC(encoding=3, mime=mime, type=3, desc='Cover', data=metadata["album_art"]))
                        try:
                            temp_file.seek(0)
                            id3.save(temp_file)
                            logger.info("MP3 metadata embedded successfully")
                        except Exception as e:
                            logger.warning(f"Could not save MP3 ID3 tags for {file_name}: {e}. Sending original file.")
                            temp_file.seek(0)

                temp_file.seek(0)
                file_stream = temp_file

            # Upload file using Pyrogram
            await self.client.send_document(
                chat_id=self.channel_id,
                document=file_stream,
                caption=caption,
                file_name=file_name
            )
            logger.info(f"Successfully uploaded: {file_name}")
            return True

        except FloodWait as e:
            logger.warning(f"Flood wait error: {e}. Waiting {e.x} seconds.")
            await asyncio.sleep(e.x)
            return await self.upload_file(file_stream, file_name, caption, metadata)
        except ChatWriteForbidden:
            logger.error("Cannot write to channel. Check bot permissions.")
            return False
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return False

    async def send_message(self, message: str) -> bool:
        """Send text message to channel"""
        try:
            await self.client.send_message(self.channel_id, message)
            return True
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    async def send_progress_update(self, message: str) -> bool:
        """Send progress update to channel"""
        try:
            timestamp = asyncio.get_event_loop().time()
            progress_message = f"⏰ {timestamp:.0f}: {message}"
            await self.client.send_message(self.channel_id, progress_message)
            return True
        except Exception as e:
            logger.error(f"Error sending progress update: {e}")
            return False

    def __del__(self):
        """Cleanup client on object deletion"""
        self.client.stop()
