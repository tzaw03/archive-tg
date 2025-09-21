#!/usr/bin/env python3
"""
Archive.org Handler Module
Handles all archive.org API interactions
"""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse
import io

logger = logging.getLogger(__name__)

class ArchiveOrgHandler:
    def __init__(self):
        self.base_url = "https://archive.org"
        self.metadata_endpoint = "/metadata/{identifier}"
        self.download_endpoint = "/download/{identifier}/{filename}"
        self.session = None
        self.current_identifier = None   # <-- keep identifier here
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_session(self):
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    def extract_identifier(self, url: str) -> Optional[str]:
        try:
            parsed = urlparse(url)
            path_parts = parsed.path.strip('/').split('/')
            
            if 'details' in path_parts:
                idx = path_parts.index('details')
                if idx + 1 < len(path_parts):
                    return path_parts[idx + 1]
            
            if len(path_parts) == 1 and path_parts[0]:
                return path_parts[0]
                
            return None
        except Exception as e:
            logger.error(f"Error extracting identifier from URL {url}: {e}")
            return None
    
    async def get_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        identifier = self.extract_identifier(url)
        if not identifier:
            logger.error("Could not extract identifier from URL")
            return None
        
        self.current_identifier = identifier   # <-- save identifier
        
        try:
            session = await self.get_session()
            metadata_url = f"{self.base_url}{self.metadata_endpoint.format(identifier=identifier)}"
            
            async with session.get(metadata_url) as response:
                if response.status == 200:
                    metadata = await response.json()
                    logger.info(f"Successfully fetched metadata for {identifier}")
                    return metadata
                else:
                    logger.error(f"Failed to fetch metadata: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error fetching metadata: {e}")
            return None
    
    def get_available_formats(self, metadata: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        formats = {}
        files = metadata.get('files', [])
        
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
            
            if file_name.endswith(('_meta.xml', '_files.xml', '_chocr.html', '_djvu.txt')):
                continue
            
            file_size = file_info.get('size', 0)
            if int(file_size) < 1024:
                continue
            
            file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
            
            for format_name, extensions in format_categories.items():
                if file_ext in extensions:
                    if format_name not in formats:
                        formats[format_name] = []
                    # add identifier for download
                    file_info['identifier'] = self.current_identifier
                    formats[format_name].append(file_info)
                    break
        
        return dict(sorted(formats.items(), key=lambda x: len(x[1]), reverse=True))
    
    async def download_file_stream(self, file_info: Dict[str, Any]) -> Optional[io.BytesIO]:
        try:
            session = await self.get_session()
            identifier = file_info.get('identifier', '')
            file_name = file_info.get('name', '')
            
            if not identifier or not file_name:
                logger.error("Missing identifier or filename")
                return None
            
            download_url = f"{self.base_url}{self.download_endpoint.format(identifier=identifier, filename=file_name)}"
            logger.info(f"Downloading: {file_name}")
            
            file_stream = io.BytesIO()
            
            async with session.get(download_url) as response:
                if response.status != 200:
                    logger.error(f"Failed to download file: {response.status}")
                    return None
                
                async for chunk in response.content.iter_chunked(8192):
                    if chunk:
                        file_stream.write(chunk)
                
                file_stream.seek(0)
                logger.info(f"Successfully downloaded: {file_name}")
                return file_stream
                
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return None
