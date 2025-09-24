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
                    try:
                        audio = FLAC(temp_file)
                    except Exception:
                        # If mutagen can't parse, just skip tagging
                        audio = None

                    if audio is not None:
                        # set standard tags
                        if metadata.get("title"):
                            audio["title"] = metadata.get("title")
                        if metadata.get("creator"):
                            audio["artist"] = metadata.get("creator")
                        if metadata.get("album"):
                            audio["album"] = metadata.get("album")
                        
                        # add picture if present
                        if "album_art" in metadata and metadata["album_art"]:
                            pic = Picture()
                            pic.data = metadata["album_art"]
                            pic.type = 3
                            # detect mime type (jpeg or png)
                            if metadata["album_art"][:4] == b'\x89PNG':
                                pic.mime = 'image/png'
                            else:
                                pic.mime = 'image/jpeg'
                            audio.add_picture(pic)
                        # save tags back into temp_file
                        try:
                            audio.save(temp_file)
                        except Exception as e:
                            logger.warning(f"Could not save FLAC tags: {e}")

                elif file_ext == 'mp3':
                    try:
                        # Try to load existing ID3 tags; if not present, create new ID3
                        try:
                            id3 = ID3(temp_file)
                        except Exception:
                            id3 = ID3()
                        
                        # set basic text tags
                        if metadata.get("title"):
                            id3.add(TIT2(encoding=3, text=metadata.get("title")))
                        if metadata.get("creator"):
                            id3.add(TPE1(encoding=3, text=metadata.get("creator")))
                        if metadata.get("album"):
                            id3.add(TALB(encoding=3, text=metadata.get("album")))
                        
                        # add album art if present
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
                        # save ID3 tags into the temp_file
                        try:
                            # When saving to a file-like object, ID3.save requires a filename or a fileobj supporting .seek and .write
                            temp_file.seek(0)
                            id3.save(temp_file)
                        except Exception as e:
                            logger.warning(f"Could not save MP3 ID3 tags: {e}")
                    except Exception as e:
                        logger.warning(f"MP3 tagging skipped due to error: {e}")
                
                # rewind after tagging
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
