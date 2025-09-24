#!/usr/bin/env python3
"""
Telegram Bot Main Application
"""

import asyncio
import logging
import os

from archive_handler import ArchiveOrgHandler
from telegram_handler import TelegramHandler

logger = logging.getLogger(__name__)

class ArchiveTelegramBot:
    def __init__(self):
        self.archive_handler = ArchiveOrgHandler()
        self.telegram_handler = TelegramHandler()
    
    async def download_and_upload_file(self, url: str, chat_id: int):
        try:
            metadata = await self.archive_handler.get_metadata(url)
            if not metadata:
                logger.error("No metadata found")
                return
            
            formats = self.archive_handler.get_available_formats(metadata)
            if not formats:
                logger.error("No downloadable formats found")
                return
            
            # Example: choose FLAC if available
            chosen_format = formats.get('FLAC') or list(formats.values())[0]
            
            for file_info in chosen_format:
                file_stream = await self.archive_handler.download_file_stream(file_info)
                if not file_stream:
                    continue
                
                # album art (fixed with .getvalue())
                album_art = None
                files = metadata.get('files', [])
                for f in files:
                    try:
                        f_size = int(f.get('size', 0))
                    except (ValueError, TypeError):
                        f_size = 0

                    if f.get('name', '').lower().endswith(('.jpg', '.jpeg', '.png')) and f_size > 1024:
                        art_stream = await self.archive_handler.download_file_stream(f)
                        if art_stream:
                            album_art = art_stream.getvalue()
                            break
                
                file_metadata = {
                    "title": file_info.get("title", file_info.get("name")),
                    "creator": metadata.get("metadata", {}).get("creator", "Unknown Artist"),
                    "album": metadata.get("metadata", {}).get("title", "Archive.org Collection"),
                    "album_art": album_art
                }
                
                await self.telegram_handler.upload_file(
                    chat_id,
                    file_stream,
                    file_info.get("name"),
                    file_metadata
                )
        
        except Exception as e:
            logger.error(f"Error downloading/uploading file: {e}")
    
    async def run(self):
        logger.info("Bot is running...")
        await self.telegram_handler.start()
