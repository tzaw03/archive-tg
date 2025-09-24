#!/usr/bin/env python3
"""
Telegram Handler Module
"""

import logging
from io import BytesIO
from pyrogram import Client
from pyrogram.types import Message
import mutagen
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, APIC

logger = logging.getLogger(__name__)

class TelegramHandler:
    def __init__(self):
        self.client = Client(
            "bot",
            api_id=int(os.getenv("API_ID")),
            api_hash=os.getenv("API_HASH"),
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN")
        )
    
    async def start(self):
        await self.client.start()
        logger.info("Telegram client started")
    
    async def upload_file(self, chat_id: int, file_stream: BytesIO, file_name: str, metadata: dict):
        try:
            file_ext = file_name.split('.')[-1].lower()
            
            # Embed metadata
            if file_ext in ['mp3', 'flac'] and metadata:
                file_stream.seek(0)
                temp_file = BytesIO(file_stream.read())
                temp_file.seek(0)
                
                if file_ext == 'flac':
                    audio = FLAC(temp_file)
                    audio["title"] = metadata.get("title", file_name)
                    audio["artist"] = metadata.get("creator", "Unknown Artist")
                    audio["album"] = metadata.get("album", "Archive.org Collection")
                    if "album_art" in metadata and metadata["album_art"]:
                        pic = Picture()
                        pic.data = metadata["album_art"]
                        pic.type = 3
                        pic.mime = "image/jpeg"
                        audio.add_picture(pic)
                    audio.save(temp_file)
                elif file_ext == 'mp3':
                    audio = ID3(temp_file)
                    audio["TIT2"] = mutagen.id3.TIT2(text=metadata.get("title", file_name))
                    audio["TPE1"] = mutagen.id3.TPE1(text=metadata.get("creator", "Unknown Artist"))
                    audio["TALB"] = mutagen.id3.TALB(text=metadata.get("album", "Archive.org Collection"))
                    if "album_art" in metadata and metadata["album_art"]:
                        audio["APIC"] = APIC(
                            encoding=3,
                            mime="image/jpeg",
                            type=3,
                            desc="Cover",
                            data=metadata["album_art"]
                        )
                    audio.save(temp_file)
                
                temp_file.seek(0)
                file_stream = temp_file
            
            file_stream.seek(0)
            await self.client.send_document(
                chat_id,
                file_stream,
                file_name=file_name
            )
            logger.info(f"Successfully uploaded {file_name} to Telegram")
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
