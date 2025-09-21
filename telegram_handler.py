#!/usr/bin/env python3
"""
Telegram Channel Handler Module
Handles all Telegram channel operations
"""

import asyncio
import logging
from typing import Optional
from io import BytesIO

from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeVideo
from telethon.errors import FloodWaitError, ChatWriteForbiddenError

logger = logging.getLogger(__name__)

class TelegramChannelHandler:
    def __init__(self, client: TelegramClient, channel_id: str):
        self.client = client
        # Ensure channel_id is int (Telethon requires numeric ID for bots)
        try:
            self.channel_id = int(channel_id)
        except ValueError:
            self.channel_id = channel_id
        
    async def upload_file(self, file_stream: BytesIO, file_name: str, caption: Optional[str] = None) -> bool:
        """Upload file to Telegram channel"""
        try:
            # Determine file type and attributes
            file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
            attributes = []
            
            if file_ext in ['mp3', 'flac', 'wav', 'ogg']:
                attributes.append(DocumentAttributeAudio(
                    duration=0,  # auto-detected
                    title=file_name,
                    performer=None
                ))
            elif file_ext in ['mp4', 'mkv', 'avi']:
                attributes.append(DocumentAttributeVideo(
                    duration=0,  # auto-detected
                    w=0,
                    h=0
                ))
            
            # Upload file
            logger.info(f"Uploading {file_name} to channel...")
            file_stream.seek(0)  # Reset stream position
            
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
            return await self.upload_file(file_stream, file_name, caption)
            
        except ChatWriteForbiddenError:
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
            await self.send_message(progress_message)
            return True
        except Exception as e:
            logger.error(f"Error sending progress update: {e}")
            return False
