#!/usr/bin/env python3
"""
Telegram Channel Handler Module
Handles all Telegram channel operations, including metadata embedding.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from io import BytesIO

from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeAudio
from telethon.errors import FloodWaitError, ChatWriteForbiddenError

import mutagen
from mutagen.flac import Picture as FLACPicture
from mutagen.id3 import APIC

logger = logging.getLogger(__name__)

class TelegramChannelHandler:
    def __init__(self, client: TelegramClient, channel_id: int):
        self.client = client
        self.channel_id = channel_id

    def embed_metadata(self, file_stream: BytesIO, file_name: str, metadata: Dict[str, Any], art_stream: Optional[BytesIO]) -> BytesIO:
        output_stream = BytesIO()
        try:
            file_stream.seek(0)
            audio = mutagen.File(file_stream, easy=True)
            if audio is None: raise ValueError("Cannot process audio file.")

            audio.delete()
            if metadata.get('title'): audio['title'] = metadata['title']
            if metadata.get('artist'): audio['artist'] = metadata['artist']
            if metadata.get('album'): audio['album'] = metadata['album']
            if metadata.get('date'): audio['date'] = metadata['date']
            audio.save()

            file_stream.seek(0)
            audio_full = mutagen.File(file_stream)
            if art_stream:
                art_stream.seek(0)
                art_data = art_stream.read()
                if file_name.lower().endswith('.flac'):
                    pic = FLACPicture()
                    pic.type = 3
                    pic.mime = 'image/jpeg'
                    pic.data = art_data
                    audio_full.add_picture(pic)
                elif file_name.lower().endswith('.mp3'):
                    audio_full.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=art_data))
            
            audio_full.save(output_stream)
            output_stream.seek(0)
            return output_stream
        except Exception as e:
            logger.error(f"Mutagen error for {file_name}: {e}. Sending original file.")
            file_stream.seek(0)
            return file_stream

    async def upload_file(self, file_stream: BytesIO, file_name: str, caption: str, metadata: Dict[str, Any]) -> bool:
        try:
            attributes = []
            if file_name.lower().endswith(('.mp3', '.flac', '.wav', '.ogg')):
                attributes.append(DocumentAttributeAudio(
                    duration=0,
                    title=metadata.get('title', file_name),
                    performer=metadata.get('artist', "Unknown Artist")
                ))

            await self.client.send_file(
                self.channel_id,
                file=file_stream,
                caption=caption,
                attributes=attributes,
                force_document=False,
                supports_streaming=True
            )
            return True
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            return await self.upload_file(file_stream, file_name, caption, metadata)
        except Exception as e:
            logger.error(f"Error uploading {file_name}: {e}")
            return False
