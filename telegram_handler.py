#!/usr/bin/env python3
"""
Telegram Channel Handler Module
Telegram channel operations တွေကို ကိုင်တွယ်ပါ
"""

import asyncio
import logging
from typing import Optional, IO
from io import BytesIO

from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeVideo
from telethon.errors import FloodWaitError, ChatWriteForbiddenError

logger = logging.getLogger(__name__)

class TelegramChannelHandler:
    def __init__(self, client: TelegramClient, channel_id: str):
        self.client = client
        self.channel_id = channel_id
        
    async def upload_file(self, file_stream: BytesIO, file_name: str, caption: str) -> bool:
        """File ကို Telegram channel ထဲ upload လုပ်ပါ"""
        try:
            # File type ကို စစ်ပါ
            file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
            
            # File type အလိုက် attributes သတ်မှတ်ပါ
            attributes = []
            
            if file_ext in ['mp3', 'flac', 'wav', 'ogg']:
                attributes.append(DocumentAttributeAudio(
                    duration=0,  # Auto-detect
                    title=file_name,
                    performer="Archive.org"
                ))
            elif file_ext in ['mp4', 'mkv', 'avi']:
                attributes.append(DocumentAttributeVideo(
                    duration=0,  # Auto-detect
                    w=0,  # Auto-detect
                    h=0   # Auto-detect
                ))
            
            # Upload
            logger.info(f"{file_name} ကို channel ထဲ upload လုပ်နေပါသည်...")
            
            file_stream.seek(0)  # Stream position reset
            
            # Channel ထဲ file ပို့ပါ
            await self.client.send_file(
                self.channel_id,
                file_stream,
                caption=caption,
                file_name=file_name,
                attributes=attributes,
                allow_cache=False,
                force_document=False,  # Telegram ကို ဆုံးဖြတ်ခွင့်ပေး
                supports_streaming=True
            )
            
            logger.info(f"Upload successful: {file_name}")
            return True
            
        except FloodWaitError as e:
            logger.warning(f"Flood wait error: {e}")
            await asyncio.sleep(e.seconds)
            return await self.upload_file(file_stream, file_name, caption)
            
        except ChatWriteForbiddenError:
            logger.error("Channel ထဲ write လုပ်ခွင့်မရှိပါ")
            return False
            
        except Exception as e:
            logger.error(f"File upload error: {e}")
            return False
    
    async def send_message(self, message: str) -> bool:
        """Text message ပို့ပါ"""
        try:
            await self.client.send_message(self.channel_id, message)
            return True
        except Exception as e:
            logger.error(f"Message send error: {e}")
            return False
    
    async def send_progress_update(self, message: str) -> bool:
        """Progress update ပို့ပါ"""
        tryaexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_session(self):
        """aiohttp session ရယူပါ"""
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    def extract_identifier(self, url: str) -> Optional[str]:
        """archive.org URL ကနေ identifier ရယူပါ"""
        try:
            parsed = urlparse(url)
            path_parts = parsed.path.strip('/').split('/')
            
            if 'details' in path_parts:
                idx = path_parts.index('details')
                if idx + 1 < len(path_parts):
                    return path_parts[idx + 1]
            
            # Direct identifier URLs
            if len(path_parts) == 1 and path_parts[0]:
                return path_parts[0]
                
            return None
        except Exception as e:
            logger.error(f"URL {url} ကနေ identifier ရယူရာမှာ error: {e}")
            return None
    
    async def get_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """archive.org item အတွက် metadata ရယူပါ"""
        identifier = self.extract_identifier(url)
        if not identifier:
            logger.error("URL ကနေ identifier မရနိုင်ပါ")
            return None
        
        try:
            session = await self.get_session()
            metadata_url = f"{self.base_url}{self.metadata_endpoint.format(identifier=identifier)}"
            
            async with session.get(metadata_url) as response:
                if response.status == 200:
                    metadata = await response.json()
                    logger.info(f"{identifier} အတွက် metadata ရယူပြီးပါပြီ")
                    return metadata
                else:
                    logger.error(f"Metadata မရနိုင်ပါ: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Metadata ရယူရာမှာ error: {e}")
            return None
    
    def get_available_formats(self, metadata: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Metadata ကနေ download လုပ်နိုင်သော format တွေရယူပါ"""
        formats = {}
        files = metadata.get('files', [])
        
        # Format categories
        format_categories = {
            'FLAC': ['flac'],
            'MP3': ['mp3'],
            'WAV': ['wav'],
            'OGG': ['ogg', 'oga'],
            'MP4': ['mp4', 'm4v'],
            'MKV': ['mkv'],
            'AVI': ['avi'],
            'PDF': ['pdf'],
            'EPUB': ['epub'],
            'TXT': ['txt'],
            'JPG': ['jpg', 'jpeg'],
            'PNG': ['png'],
            'GIF': ['gif'],
            'ZIP': ['zip'],
            'TORRENT': ['torrent']
        }
        
        for file_info in files:
            file_name = file_info.get('name', '')
            if not file_name:
                continue
            
            # Metadata files တွေကို skip လုပ်ပါ
            if file_name.endswith(('_meta.xml', '_files.xml', '_chocr.html', '_djvu.txt')):
                continue
            
            # Small files တ
