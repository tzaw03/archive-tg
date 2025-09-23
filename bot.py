# [Keep the existing imports and class definition unchanged until the method]

async def download_and_upload_file(self, file_info: Dict[str, Any], metadata: Dict[str, Any], format_name: str) -> bool:
    """Download file from archive.org and upload to Telegram channel"""
    try:
        # Download file stream
        file_stream = await self.archive_handler.download_file_stream(file_info)
        
        if not file_stream:
            return False
        
        # Get file metadata
        file_name = file_info['name']
        file_size = file_info.get('size', 0)
        
        # Get item metadata for caption and embedding
        item_metadata = metadata.get('metadata', {})
        title = item_metadata.get('title', 'Unknown Title')
        creator = item_metadata.get('creator', 'Unknown Creator')
        date = item_metadata.get('date', 'Unknown Date')
        
        # Attempt to get album art from metadata (if available)
        album_art = None
        files = metadata.get('files', [])
        for f in files:
            if f.get('name', '').lower().endswith(('.jpg', '.jpeg', '.png')) and f.get('size', 0) > 1024:
                art_stream = await self.archive_handler.download_file_stream(f)
                if art_stream:
                    album_art = art_stream.read()
                    break
        
        # Prepare metadata for embedding
        embed_metadata = {
            "title": title,
            "creator": creator,
            "album": item_metadata.get('collection', 'Archive.org'),
            "album_art": album_art
        }
        
        # Create caption
        caption = f"""
📁 **{title}**
📅 {date}
💾 {format_name} format
📊 {self.format_file_size(file_size)}
        """.strip()
        
        # Upload to channel with embedded metadata
        success = await self.channel_handler.upload_file(
            file_stream, file_name, caption, metadata=embed_metadata
        )
        
        return success
        
    except Exception as e:
        logger.error(f"Error downloading/uploading file: {e}")
        return False
