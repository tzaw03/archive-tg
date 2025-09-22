# telegram_handler.py
import logging
import asyncio
from typing import Optional
import io

from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChatWriteForbiddenError

logger = logging.getLogger(__name__)

class TelegramChannelHandler:
    def __init__(self, client: TelegramClient, channel_id: int):
        self.client = client
        self.channel_id = channel_id

    async def send_message(self, message: str) -> bool:
        """Send a text message to the channel"""
        try:
            await self.client.send_message(self.channel_id, message, parse_mode='markdown')
            return True
        except (FloodWaitError, ChatWriteForbiddenError) as e:
            logger.error(f"Failed to send message: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending message: {e}")
            return False

    async def upload_file(self, file_stream: io.BytesIO, file_name: str, caption: str = "", thumb: Optional[io.BytesIO] = None) -> bool:
        """Upload a file to the channel with optional thumbnail and caption"""
        try:
            file_stream.seek(0)  # Ensure stream is at the beginning
            if thumb:
                thumb.seek(0)  # Ensure thumb stream is at the beginning
            await self.client.send_file(
                self.channel_id,
                file=file_stream,
                caption=caption,
                thumb=thumb,
                supports_streaming=True,
                progress_callback=lambda d, t: logger.info(f"Uploading: {d}/{t} bytes")
            )
            logger.info(f"Uploaded file: {file_name}")
            return True
        except (FloodWaitError, ChatWriteForbiddenError) as e:
            logger.error(f"Failed to upload file {file_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error uploading file {file_name}: {e}")
            return False
        finally:
            if thumb:
                try:
                    thumb.close()
                except:
                    pass
