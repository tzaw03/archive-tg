#!/usr/bin/env python3
"""
Telegram Channel Handler Module
Handles metadata embedding on disk and Telegram uploads.
"""
import asyncio
import logging
from typing import Optional, Dict, Any

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

    def embed_metadata(self, file_path: str, track_meta: Dict[str, Any], art_path: Optional[str]) -> bool:
        """Embeds metadata and album art into a file on disk."""
        try:
            audio = mutagen.File(file_path, easy=True)
            if audio is None: raise ValueError("Mutagen could not recognize the audio format from file.")

            audio.delete()
            if track_meta.get('title'): audio['title'] = track_meta['title']
            if track_meta.get('artist'): audio['artist'] = track_meta['artist']
            if track_meta.get('album'): audio['album'] = track_meta['album']
            if track_meta.get('date'): audio['date'] = track_meta['date']
            audio.save()

            audio_full = mutagen.File(file_path)
            if art_path and audio_full is not None:
                with open(art_path, 'rb') as art_f:
                    art_data = art_f.read()
                
                file_name_lower = file_path.lower()
                if file_name_lower.endswith('.flac'):
                    pic = FLACPicture()
                    pic.type = 3
                    pic.mime = 'image/jpeg'
                    pic.data = art_data
                    audio_full.add_picture(pic)
                elif file_name_lower.endswith('.mp3'):
                    audio_full.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=art_data))
                
                audio_full.save()

            logger.info(f"Successfully embedded metadata for {os.path.basename(file_path)}")
            return True
            
        except Exception as e:
            logger.error(f"METADATA EMBEDDING FAILED for {os.path.basename(file_path)}: {e}")
            return False

    async def upload_file(self, file_path: str, caption: str, track_meta: Dict[str, Any]) -> bool:
        """Uploads a file from disk to Telegram."""
        file_name = os.path.basename(file_path)
        try:
            attributes = []
            if file_name.lower().endswith(('.mp3', '.flac', '.wav', '.ogg')):
                attributes.append(DocumentAttributeAudio(
                    duration=0,
                    title=track_meta.get('title', file_name),
                    performer=track_meta.get('artist', "Unknown Artist")
                ))

            await self.client.send_file(
                self.channel_id,
                file=file_path,
                caption=caption,
                attributes=attributes,
                force_document=False,
                supports_streaming=True
            )
            return True
        except FloodWaitError as e:
            logger.warning(f"Flood wait of {e.seconds} seconds required. Sleeping...")
            await asyncio.sleep(e.seconds)
            return await self.upload_file(file_path, caption, track_meta)
        except Exception as e:
            logger.error(f"Failed to upload {file_name}: {e}")
            return False
