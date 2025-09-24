#!/usr/bin/env python3
"""
Telegram Channel Handler Module
Handles metadata embedding and Telegram uploads.
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from io import BytesIO

from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeAudio
from telethon.errors import FloodWaitError

import mutagen
from mutagen.flac import Picture as FLACPicture
from mutagen.id3 import APIC

logger = logging.getLogger(__name__)

class TelegramChannelHandler:
    def __init__(self, client: TelegramClient, channel_id: int):
        self.client = client
        self.channel_id = channel_id

    def embed_metadata(self, file_stream: BytesIO, file_name: str, track_meta: Dict[str, Any], art_stream: Optional[BytesIO]) -> BytesIO:
        """
        Embeds metadata and album art into an audio file stream.
        This is the core function to solve the main problem.
        """
        output_stream = BytesIO()
        try:
            file_stream.seek(0)
            
            # CRITICAL FIX: Use 'fileobj' keyword argument for mutagen
            audio = mutagen.File(fileobj=file_stream, easy=True)
            if audio is None:
                raise ValueError("Mutagen could not recognize the audio format from stream.")

            # Clear existing tags and apply new ones
            audio.delete()
            if track_meta.get('title'): audio['title'] = track_meta['title']
            if track_meta.get('artist'): audio['artist'] = track_meta['artist']
            if track_meta.get('album'): audio['album'] = track_meta['album']
            if track_meta.get('date'): audio['date'] = track_meta['date']
            audio.save()

            file_stream.seek(0)
            # Re-open with full object to add picture
            audio_full = mutagen.File(fileobj=file_stream)
            if art_stream and audio_full is not None:
                art_stream.seek(0)
                art_data = art_stream.read()
                
                if file_name.lower().endswith('.flac'):
                    pic = FLACPicture()
                    pic.type = 3  # Cover (front)
                    pic.mime = 'image/jpeg'
                    pic.data = art_data
                    audio_full.add_picture(pic)
                elif file_name.lower().endswith('.mp3'):
                    audio_full.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=art_data))
            
            audio_full.save(output_stream)
            output_stream.seek(0)
            logger.info(f"Successfully embedded metadata for {file_name}")
            return output_stream
            
        except Exception as e:
            logger.error(f"METADATA EMBEDDING FAILED for {file_name}: {e}. Sending original file.")
            file_stream.seek(0)
            return file_stream

    async def upload_file(self, file_stream: BytesIO, file_name: str, caption: str, track_meta: Dict[str, Any]) -> bool:
        """Uploads the processed file to Telegram."""
        try:
            attributes = []
            if file_name.lower().endswith(('.mp3', '.flac', '.wav', '.ogg')):
                attributes.append(DocumentAttributeAudio(
                    duration=0, # Telegram will auto-detect
                    title=track_meta.get('title', file_name),
                    performer=track_meta.get('artist', "Unknown Artist")
                ))

            await self.client.send_file(
                self.channel_id,
                file=file_stream,
                caption=caption,
                attributes=attributes,
                force_document=False, # Let Telegram decide best display (audio or file)
                supports_streaming=True
            )
            return True
        except FloodWaitError as e:
            logger.warning(f"Flood wait of {e.seconds} seconds required. Sleeping...")
            await asyncio.sleep(e.seconds)
            return await self.upload_file(file_stream, file_name, caption, track_meta) # Retry
        except Exception as e:
            logger.error(f"Failed to upload {file_name}: {e}")
            return False
