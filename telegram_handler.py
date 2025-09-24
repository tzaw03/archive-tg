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
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB
from telethon import TelegramClient
from telethon.tl.types import InputPeerChannel, DocumentAttributeAudio, DocumentAttributeVideo
from telethon.errors import FloodWaitError, ChatWriteForbiddenError

logger = logging.getLogger(__name__)

class TelegramChannelHandler:
    def __init__(self, client: TelegramClient, channel_id: str):
        self.client = client
        self.channel_id = channel_id  # Store as string (e.g., "-1003031099376")
    
    async def upload_file(self, file_stream: BytesIO, file_name: str, caption: str, metadata: dict = None) -> bool:
        """Upload file to Telegram channel with embedded metadata"""
        try:
            # Resolve channel entity with proper handling for private channel ID
            try:
                # Ensure channel_id starts with "-100" for private channels
                if not self.channel_id.startswith('-100'):
                    logger.error(f"Invalid channel ID format: {self.channel_id}. Expected format: '-100xxxxxxx'.")
                    return False
                
                # Convert string ID to InputPeerChannel
                entity = await self.client.get_entity(self.channel_id)
                if not hasattr(entity, 'channel_id'):
                    logger.error(f"Failed to resolve channel entity for ID: {self.channel_id}. Ensure bot is invited and has permissions.")
                    return False
                logger.info(f"Successfully resolved channel entity for ID: {self.channel_id}")
            except ValueError as e:  # Use built-in ValueError
                logger.error(f"Invalid channel ID format: {e}. Please ensure CHANNEL_ID is correct (e.g., '-1003031099376').")
                return False
            except Exception as e:
                logger.error(f"Failed to get channel entity: {e}. Check CHANNEL_ID ('{self.channel_id}') and ensure bot is added as admin with 'Post messages' rights.")
                return False
            
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
                                if metadata["album_art"][:4] == b'\x89PNG':
                                    pic.mime = 'image/png'
                                else:
                                    pic.mime = 'image/jpeg'
                                audio.add_picture(pic)
                            
                            audio.save(temp_file)
                            logger.info("FLAC metadata embedded successfully")
                    except Exception as e:
                        logger.warning(f"Mutagen error for FLAC {file_name}: {e}. Sending original file without metadata.")
                        temp_file.seek(0)  # Reset to original position
                
                elif file_ext == 'mp3':
                    try:
                        id3 = ID3(temp_file)
                    except mutagen.id3.ID3NoHeaderError:
                        id3 = ID3()
                    except Exception as e:
                        logger.warning(f"Mutagen error for MP3 {file_name}: {e}. Sending original file without metadata.")
                        id3 = None
                    
                    if id3 is not None:
                        if metadata.get("title"):
                            id3.add(TIT2(encoding=3, text=metadata["title"]))
                        if metadata.get("creator"):
                            id3.add(TPE1(encoding=3, text=metadata["creator"]))
                        if metadata.get("album"):
                            id3.add(TALB(encoding=3, text=metadata["album"]))
                        
                        if "album_art" in metadata and metadata["album_art"]:
                            mime = 'image/jpeg'
                            if metadata["album_art"][:4] == b'\x89PNG':
                                mime = 'image/png'
                            id3.add(APIC(
                                encoding=3,
                                mime=mime,
                                type=3,
                                desc='Cover',
                                data=metadata["album_art"]
                            ))
                        
                        try:
                            temp_file.seek(0)
                            id3.save(temp_file)
                            logger.info("MP3 metadata embedded successfully")
                        except Exception as e:
                            logger.warning(f"Could not save MP3 ID3 tags for {file_name}: {e}. Sending original file without metadata.")
                            temp_file.seek(0)  # Reset to original position
                
                temp_file.seek(0)
                file_stream = temp_file
            
            # Upload file
            logger.info(f"Uploading {file_name} to channel...")
            file_stream.seek(0)
            
            await self.client.send_file(
                entity,  # Use resolved entity
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
    
    async def send_message(self, message: str) -> bool:
        """Send text message to channel"""
        try:
            entity = await self.client.get_entity(self.channel_id)
            await self.client.send_message(entity, message)
            return True
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    async def send_progress_update(self, message: str) -> bool:
        """Send progress update to channel"""
        try:
            entity = await self.client.get_entity(self.channel_id)
            # Add timestamp to message
            timestamp = asyncio.get_event_loop().time()
            progress_message = f"⏰ {timestamp:.0f}: {message}"
            await self.client.send_message(entity, progress_message)
            return True
        except Exception as e:
            logger.error(f"Error sending progress update: {e}")
            return False
