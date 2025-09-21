#!/usr/bin/env python3
"""
Telegram Channel Handler Module
Handles sending messages and uploading files to a Telegram channel
"""

import logging
from telethon import TelegramClient

logger = logging.getLogger(__name__)

class TelegramChannelHandler:
    def __init__(self, client: TelegramClient, channel_id: str):
        self.client = client
        self.channel_id = channel_id

    async def send_message(self, text: str):
        """Send plain text message to the Telegram channel"""
        try:
            await self.client.send_message(self.channel_id, text)
            logger.info("Message sent successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def upload_file(self, file_stream, file_name: str, caption: str = None, thumb=None):
        """Upload a file to the Telegram channel"""
        try:
            # Reset stream pointer to start before upload
            if hasattr(file_stream, "seek"):
                file_stream.seek(0)

            await self.client.send_file(
                self.channel_id,
                file=file_stream,
                caption=caption,
                file_name=file_name,
                thumb=thumb
            )
            logger.info(f"Uploaded file: {file_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload file {file_name}: {e}")
            return False
