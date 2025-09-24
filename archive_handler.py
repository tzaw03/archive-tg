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
        
        if not files:
            logger.error("No files found in metadata")
            return formats
        
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
                logger.warning(f"File info missing name: {file_info}")
                continue
            
            # Skip metadata files
            if file_name.endswith(('_meta.xml', '_files.xml', '_chocr.html', '_djvu.txt')):
                continue
            
            # Safely parse file size
            raw_size = file_info.get('size', 0)
            try:
                file_size = int(raw_size)
            except (ValueError, TypeError):
                file_size = 0
            
            # Skip very small files (likely thumbnails or metadata)
            if file_size < 1024:  
                continue
            
            file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
            
            # Find matching format category
            for format_name, extensions in format_categories.items():
                if file_ext in extensions:
                    if format_name not in formats:
                        formats[format_name] = []
                    # Ensure identifier is present, use metadata identifier as fallback
                    file_info_with_id = file_info.copy()
                    if 'identifier' not in file_info_with_id:
                        file_info_with_id['identifier'] = metadata.get('metadata', {}).get('identifier', '')
                    formats[format_name].append(file_info_with_id)
                    break
        
        # Sort formats by file count
        return dict(sorted(formats.items(), key=lambda x: len(x[1]), reverse=True))
    
    async def download_file_stream(self, file_info: Dict[str, Any]) -> Optional[io.BytesIO]:
        """Download file as stream"""
        try:
            session = await self.get_session()
            
            # Construct download URL
            identifier = file_info.get('identifier', '')
            file_name = file_info.get('name', '')
            
            if not identifier or not file_name:
                logger.error(f"Missing identifier or filename in file_info: {file_info}")
                return None
            
            download_url = f"{self.base_url}{self.download_endpoint.format(identifier=identifier, filename=file_name)}"
            
            logger.info(f"Downloading: {file_name}")
            
            # Download file in chunks
            file_stream = io.BytesIO()
            
            async with session.get(download_url) as response:
                if response.status != 200:
                    logger.error(f"Failed to download file: {response.status}")
                    return None
                
                # Ensure content-length is an integer
                content_length = response.headers.get('content-length', None)
                if content_length is None:
                    total_size = 0
                else:
                    try:
                        total_size = int(content_length)
                    except (ValueError, TypeError):
                        total_size = 0
                
                downloaded = 0
                
                async for chunk in response.content.iter_chunked(8192):
                    if chunk:
                        file_stream.write(chunk)
                        downloaded += len(chunk)
                        
                        # Log progress for large files
                        if total_size > 0 and total_size > 10 * 1024 * 1024:  # Files larger than 10MB
                            progress = (downloaded / total_size) * 100
                            if int(progress) % 10 == 0:  # Log every 10%
                                logger.info(f"Download progress: {progress:.1f}%")
                
                file_stream.seek(0)
                logger.info(f"Successfully downloaded: {file_name} ({self.format_file_size(downloaded)})")
                return file_stream
                
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
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
