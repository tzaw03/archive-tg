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
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_session(self) -> aiohttp.ClientSession:
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
                response.raise_for_status()
                metadata = await response.json()
                # Add identifier to metadata for later use
                if 'files' in metadata:
                    for f in metadata['files']:
                        if 'identifier' not in f:
                            f['identifier'] = identifier
                logger.info(f"Successfully fetched metadata for {identifier}")
                return metadata
                    
        except aiohttp.ClientError as e:
            logger.error(f"Failed to fetch metadata for {identifier}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching metadata: {e}")
            return None
    
    def get_available_formats(self, metadata: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Get available download formats from metadata"""
        formats = {}
        files = metadata.get('files', [])
        
        format_categories = {
            'FLAC': ['flac'], 'MP3': ['mp3'], 'WAV': ['wav'], 'OGG': ['ogg', 'oga'],
            'MP4': ['mp4'], 'MKV': ['mkv'], 'PDF': ['pdf'], 'EPUB': ['epub']
        }
        
        for file_info in files:
            file_name = file_info.get('name', '')
            source = file_info.get('source')
            if not file_name or source != 'original':
                continue

            file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
            
            for format_name, extensions in format_categories.items():
                if file_ext in extensions:
                    if format_name not in formats:
                        formats[format_name] = []
                    formats[format_name].append(file_info)
                    break
        
        return dict(sorted(formats.items(), key=lambda x: len(x[1]), reverse=True))

    async def download_file_stream(self, identifier: str, filename: str) -> Optional[io.BytesIO]:
        """Download file as a BytesIO stream"""
        session = await self.get_session()
        download_url = f"{self.base_url}{self.download_endpoint.format(identifier=identifier, filename=filename)}"
        
        try:
            logger.info(f"Downloading stream for: {filename}")
            async with session.get(download_url) as response:
                response.raise_for_status()
                content = await response.read()
                logger.info(f"Successfully downloaded stream for: {filename}")
                return io.BytesIO(content)
        except aiohttp.ClientError as e:
            logger.error(f"Failed to download file {filename}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error downloading file stream for {filename}: {e}")
            return None
            
    async def get_album_art_stream(self, metadata: Dict[str, Any]) -> Optional[io.BytesIO]:
        """Finds and downloads the album art as a BytesIO stream."""
        files = metadata.get('files', [])
        identifier = metadata.get('metadata', {}).get('identifier')
        
        if not identifier:
            return None
            
        # Prioritized list of common cover art filenames
        art_candidates = ['cover.jpg', 'folder.jpg', 'front.jpg']
        art_file_to_download = None

        # First, check for common names
        for file_info in files:
            if file_info.get('name', '').lower() in art_candidates:
                art_file_to_download = file_info['name']
                break
        
        # If not found, check metadata for a specified image
        if not art_file_to_download and metadata.get('misc', {}).get('image'):
            art_file_to_download = metadata['misc']['image']

        # If still not found, take the first available JPG or PNG
        if not art_file_to_download:
            for file_info in files:
                file_name = file_info.get('name', '').lower()
                if file_name.endswith('.jpg') or file_name.endswith('.jpeg') or file_name.endswith('.png'):
                     art_file_to_download = file_info['name']
                     break
        
        if art_file_to_download:
            logger.info(f"Found album art: {art_file_to_download}")
            return await self.download_file_stream(identifier, art_file_to_download)
        
        logger.warning("No album art found for this item.")
        return None
