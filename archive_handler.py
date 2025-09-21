#!/usr/bin/env python3
"""
Archive.org Handler Module
archive.org API ကိုအသုံးပြုပြီး file တွေကို download လုပ်ပါ
"""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse, parse_qs
import io

logger = logging.getLogger(__name__)

class ArchiveOrgHandler:
    def __init__(self):
        self.base_url = "https://archive.org"
        self.metadata_endpoint = "/metadata/{identifier}"
        self.download_endpoint = "/download/{identifier}/{filename}"
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_session(self):
        """aiohttp session ရယူပါ"""
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    def extract_identifier(self, url: str) -> Optional[str]:
        """archive.org URL ကနေ identifier ကို extract လုပ်ပါ"""
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
            logger.error(f"URL {url} ကနေ identifier extract မရပါ: {e}")
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
        """Metadata ကနေ download လုပ်နိုင်သော format တွေကို ရယူပါ"""
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
            
            # Small files တွေကို skip လုပ်ပါ
            file_size = file_info.get('size', 0)
            if int(file_size) < 1024:  # 1KB ထက်သေးတဲ့ files
                continue
            
            file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
            
            # Format category ရှာပါ
            for format_name, extensions in format_categories.items():
                if file_ext in extensions:
                    if format_name not in formats:
                        formats[format_name] = []
                    formats[format_name].append(file_info)
                    break
        
        # File count အရ sort လုပ်ပါ
        return dict(sorted(formats.items(), key=lambda x: len(x[1]), reverse=True))
    
    async def download_file_stream(self, file_info: Dict[str, Any]) -> Optional[io.BytesIO]:
        """File ကို stream အနေနဲ့ download လုပ်ပါ"""
        try:
            session = await self.get_session()
            
            # Download URL ဖန်တီးပါ
            identifier = file_info.get('identifier', '')
            file_name = file_info.get('name', '')
            
            if not identifier or not file_name:
                logger.error("Identifier or filename မရှိပါ")
                return None
            
            download_url = f"{self.base_url}{self.download_endpoint.format(identifier=identifier, filename=file_name)}"
            
            logger.info(f"Downloading: {file_name}")
            
            # Stream download
            file_stream = io.BytesIO()
            
            async with session.get(download_url) as response:
                if response.status != 200:
                    logger.error(f"File download မအောင်မြင်ပါ: {response.status}")
                    return None
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                async for chunk in response.content.iter_chunked(8192):
                    if chunk:
                        file_stream.write(chunk)
                        downloaded += len(chunk)
                        
                        # Large files အတွက် progress log
                        if total_size > 10 * 1024 * 1024:  # 10MB ထက်ကြီး
                            progress = (downloaded / total_size) * 100
                            if int(progress) % 10 == 0:  # 10% တိုင်းမှာ log
                                logger.info(f"Download progress: {progress:.1f}%")
                
                file_stream.seek(0)
                logger.info(f"Download successful: {file_name} ({self.format_file_size(downloaded)})")
                return file_stream
                
        except Exception as e:
            logger.error(f"File download error: {e}")
            return None
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """File size """
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
