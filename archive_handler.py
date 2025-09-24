#!/usr/bin/env python3
"""
Archive.org Handler Module
Handles all archive.org API interactions
"""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Any, Optional, Tuple
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
        """Get or create aiohttp session"""
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    def extract_identifier(self, url: str) -> Optional[str]:
        """Extract identifier from archive.org URL"""
        try:
            parsed = urlparse(url)
            path_parts = parsed.path.strip('/').split('/')
            
            if 'details' in path_parts:
                idx = path_parts.index('details')
                if idx + 1 < len(path_parts):
                    return path_parts[idx + 1]
            
            # Handle direct identifier URLs
            if len(path_parts) == 1 and path_parts[0]:
                return path_parts[0]
                
            return None
        except Exception as e:
            logger.error(f"Error extracting identifier from URL {url}: {e}")
            return None
    
    async def get_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """Get metadata for archive.org item"""
        identifier = self.extract_identifier(url)
        if not identifier:
            logger.error("Could not extract identifier from URL")
            return None
        
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
        """Get available download formats from metadata"""
        formats = {}
        files = metadata.get('files', [])
        
        # Define format categories
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
            
            # Skip metadata files
            if file_name.endswith(('_meta.xml', '_files.xml', '_chocr.html', '_djvu.txt')):
                continue
            
            # Skip small files (likely thumbnails or metadata)
            file_size = file_info.get('size', 0)
            if int(file_size) < 1024:  # Less than 1KB
                continue
            
            file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
            
            # Find matching format category
            for format_name, extensions in format_categories.items():
                if file_ext in extensions:
                    if format_name not in formats:
                        formats[format_name] = []
                    formats[format_name].append(file_info)
                    break
        
        # Sort formats by file count
        return dict(sorted(formats.items(), key=lambda x: len(x[1]), reverse=True))
    
    async def download_file_stream(self, identifier: str, file_name: str) -> Optional[io.BytesIO]:
        """Download file as stream"""
        try:
            session = await self.get_session()
            
            if not identifier or not file_name:
                logger.error("Missing identifier or filename")
                return None
            
            download_url = f"{self.base_url}{self.download_endpoint.format(identifier=identifier, filename=file_name)}"
            
            logger.info(f"Downloading: {file_name}")
            
            # Download file in chunks
            file_stream = io.BytesIO()
            
            async with session.get(download_url) as response:
                if response.status != 200:
                    logger.error(f"Failed to download file: {response.status}")
                    return None
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                async for chunk in response.content.iter_chunked(8192):
                    if chunk:
                        file_stream.write(chunk)
                        downloaded += len(chunk)
                        
                        # Log progress for large files
                        if total_size > 10 * 1024 * 1024:  # Files larger than 10MB
                            progress = (downloaded / total_size) * 100
                            if int(progress) % 10 == 0:  # Log every 10%
                                logger.info(f"Download progress: {progress:.1f}%")
                
                file_stream.seek(0)
                logger.info(f"Successfully downloaded: {file_name} ({self.format_file_size(downloaded)})")
                return file_stream
                
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return None
    
    async def get_item_thumbnail(self, identifier: str) -> Optional[Tuple[io.BytesIO, str]]:
        """Get item thumbnail stream and MIME type"""
        try:
            # Try standard thumbnail service
            thumb_url = f"https://archive.org/services/img/{identifier}"
            session = await self.get_session()
            
            async with session.get(thumb_url, allow_redirects=True) as response:
                if response.status == 200:
                    mime = response.headers.get('Content-Type', 'image/jpeg')
                    stream = io.BytesIO(await response.read())
                    logger.info(f"Successfully fetched thumbnail from service for {identifier}")
                    return stream, mime
            
            # Fallback to metadata files
            metadata = await self.get_metadata(f"https://archive.org/details/{identifier}")
            if not metadata:
                return None
            
            files = metadata.get('files', [])
            thumb_candidates = []
            
            for file_info in files:
                file_name = file_info.get('name', '').lower()
                file_format = file_info.get('format', '').lower()
                
                if file_format in ['jpeg', 'jpg', 'png'] and ('thumb' in file_name or 'cover' in file_name or 'art' in file_name):
                    thumb_candidates.append(file_info)
            
            if thumb_candidates:
                # Prefer the one with 'thumb' in name
                thumb_candidates.sort(key=lambda x: 'thumb' in x['name'].lower(), reverse=True)
                selected = thumb_candidates[0]
                stream = await self.download_file_stream(identifier, selected['name'])
                if stream:
                    mime = 'image/png' if selected['name'].lower().endswith('.png') else 'image/jpeg'
                    logger.info(f"Successfully fetched fallback thumbnail: {selected['name']}")
                    return stream, mime
            
            logger.warning(f"No thumbnail found for {identifier}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching thumbnail: {e}")
            return None
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
