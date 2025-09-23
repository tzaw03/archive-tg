#!/usr/bin/env python3
"""
Telegram Channel Handler Module
Handles all Telegram channel operations
"""

import asyncio
import logging
from typing import Optional, IO
from io import BytesIO
import mutagen
from mutagen.flac import FLAC
from mutagen.id3 import ID3, APIC
from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeVideo
from telethon.errors import FloodWaitError, ChatWriteForbiddenError

logger = logging.getLogger(__name__)

class TelegramChannelHandler:
    def __init__(self, client: TelegramClient, channel_id: str):
        self.client = client
        self.channel_id = channel_id
    
    async def upload_file(self, file_stream: BytesIO, file_name: str, caption: str, metadata: dict = None) -> bool:
        """Upload file to Telegram channel with embedded metadata"""
        try:
            # Determine file type and attributes
            file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
            attributes = []
            
            if file_ext in ['mp3', 'flac', 'wav', 'ogg']:
                attributes.append(DocumentAttributeAudio(
                    duration=0,  # Will be auto-detected
                    title=file_name,
                    performer="Archive.org"
                ))
            elif file_ext in ['mp4', 'mkv', 'avi']:
                attributes.append(DocumentAttributeVideo(
                    duration=0,  # Will be auto-detected
                    w=0,  # Will be auto-detected
                    h=0   # Will be auto-detected
                ))
            
            # Embed metadata using Mutagen
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
                        audio["coverart"] = mutagen.flac.Picture()
                        audio["coverart"].data = metadata["album_art"]
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
            
            # Upload file
            logger.info(f"Uploading {file_name} to channel...")
            file_stream.seek(0)
            
            await self.client.send_file(
                self.channel_id,
                file_stream,
                caption=caption,
                file_name=file_name,
                attributes=attributes,
                allow_cache=False,
                force_document=False,
                supports_streaming=True
            )
            
            logger.info(f"Successfully uploaded: {file_name}")
            return True
            
        except FloodWaitError as e:
            logger.warning(f"Flood wait error: {e}")
            await asyncio.sleep(e.seconds)
            return await self.upload_file(file_stream, file_name, caption, metadata)
            
        except ChatWriteForbiddenError:
            logger.error("Cannot write to channel. Check bot permissions.")
            return False
            
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return False
    
    # [Keep the rest of the methods (send_message, send_progress_update) unchanged]
