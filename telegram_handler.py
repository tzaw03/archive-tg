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
from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeVideo
from telethon.errors import FloodWaitError, ChatWriteForbiddenError

import mutagen
from mutagen.flac import Picture as FLACPicture
from mutagen.id3 import APIC, TIT2, TPE1, TALB, TDRC

logger = logging.getLogger(__name__)

class TelegramChannelHandler:
    def __init__(self, client: TelegramClient, channel_id: str):
        self.client = client
        self.channel_id = channel_id
        
    def embed_metadata(self, file_stream: BytesIO, file_name: str, metadata: Dict[str, Any], art_stream: Optional[BytesIO]) -> BytesIO:
        """Embeds metadata and album art into an audio file stream."""
        file_ext = file_name.split('.')[-1].lower()
        output_stream = BytesIO()
        
        try:
            file_stream.seek(0)
            audio = mutagen.File(file_stream, easy=True)
            if audio is None:
                raise ValueError("Cannot process this audio file with mutagen.")

            audio.delete() # Clear existing tags

            # Add new tags
            if metadata.get('title'):
                audio['title'] = metadata['title']
            if metadata.get('artist'):
                audio['artist'] = metadata['artist']
            if metadata.get('album'):
                audio['album'] = metadata['album']
            if metadata.get('date'):
                audio['date'] = metadata['date']
            
            audio.save() # Save text tags
            
            # Re-open with full object to add picture
            file_stream.seek(0)
            audio_full = mutagen.File(file_stream)

            if art_stream:
                art_stream.seek(0)
                art_data = art_stream.read()
                
                if file_ext == 'flac':
                    pic = FLACPicture()
                    pic.type = 3  # Cover (front)
                    pic.mime = 'image/jpeg' 
                    pic.data = art_data
                    audio_full.add_picture(pic)
                elif file_ext == 'mp3':
                    audio_full.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=art_data))

            audio_full.save(output_stream)
            output_stream.seek(0)
            logger.info(f"Successfully embedded metadata for {file_name}")
            return output_stream

        except Exception as e:
            logger.error(f"Mutagen error embedding metadata for {file_name}: {e}. Sending original file.")
            file_stream.seek(0)
            return file_stream # Return original stream on failure

    async def upload_file(self, file_stream: BytesIO, file_name: str, caption: str, metadata: Dict[str, Any]) -> bool:
        """Upload file to Telegram channel"""
        try:
            attributes = []
            
            if file_name.lower().endswith(('.mp3', '.flac', '.wav', '.ogg')):
                attributes.append(DocumentAttributeAudio(
                    duration=0,
                    title=metadata.get('title', file_name),
                    performer=metadata.get('artist', "Unknown Artist")
                ))
            
            logger.info(f"Uploading {file_name} to channel...")
            await self.client.send_file(
                self.channel_id,
                file_stream,
                caption=caption,
                attributes=attributes,
                force_document=False,
                supports_streaming=True
            )
            logger.info(f"Successfully uploaded: {file_name}")
            return True
            
        except FloodWaitError as e:
            logger.warning(f"Flood wait for {e.seconds} seconds.")
            await asyncio.sleep(e.seconds)
            return await self.upload_file(file_stream, file_name, caption, metadata) # Retry
        except ChatWriteForbiddenError:
            logger.error("Bot does not have permission to write to this channel.")
            return False
        except Exception as e:
            logger.error(f"Error uploading file {file_name}: {e}")
            return False
