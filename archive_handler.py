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
            return None
        except Exception as e:
            logger.error(f"Error extracting identifier from URL {url}: {e}")
            return None

    async def get_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        identifier = self.extract_identifier(url)
        if not identifier:
            return None
        try:
            session = await self.get_session()
            metadata_url = f"{self.base_url}{self.metadata_endpoint.format(identifier=identifier)}"
            async with session.get(metadata_url) as response:
                response.raise_for_status()
                metadata = await response.json()
                if 'files' in metadata:
                    for f in metadata['files']:
                        if 'identifier' not in f:
                            f['identifier'] = identifier
                return metadata
        except Exception as e:
            logger.error(f"Error fetching metadata: {e}")
            return None

    def get_available_formats(self, metadata: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        formats = {}
        files = metadata.get('files', [])
        for file_info in files:
            format_name = file_info.get('format')
            if format_name and file_info.get('name'):
                # Ignore metadata files
                if format_name in ["Metadata", "Item Tile", "PNG Thumb"]:
                    continue
                if format_name not in formats:
                    formats[format_name] = []
                formats[format_name].append(file_info)
        return dict(sorted(formats.items(), key=lambda x: len(x[1]), reverse=True))

    async def download_file_stream(self, identifier: str, filename: str) -> Optional[io.BytesIO]:
        session = await self.get_session()
        download_url = f"{self.base_url}{self.download_endpoint.format(identifier=identifier, filename=filename)}"
        try:
            async with session.get(download_url) as response:
                response.raise_for_status()
                content = await response.read()
                return io.BytesIO(content)
        except Exception as e:
            logger.error(f"Error downloading file stream for {filename}: {e}")
            return None

    async def get_album_art_stream(self, metadata: Dict[str, Any]) -> Optional[io.BytesIO]:
        files = metadata.get('files', [])
        identifier = metadata.get('metadata', {}).get('identifier')
        if not identifier: return None

        art_candidates = ['cover.jpg', 'folder.jpg', 'front.jpg']
        art_file_to_download = None

        if metadata.get('misc', {}).get('image'):
            art_file_to_download = metadata['misc']['image']
        else:
            for file_info in files:
                if file_info.get('name', '').lower() in art_candidates:
                    art_file_to_download = file_info['name']
                    break
        
        if not art_file_to_download:
            for file_info in files:
                if file_info.get('format') == "JPEG":
                    art_file_to_download = file_info['name']
                    break

        if art_file_to_download:
            return await self.download_file_stream(identifier, art_file_to_download)
        return None
