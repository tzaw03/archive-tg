import logging
import os
from typing import Optional, Dict, Any
from pyrogram import Client
from pyrogram.types import Audio
from mutagen.flac import Picture as FLACPicture
from mutagen.id3 import APIC
import mutagen

logger = logging.getLogger(__name__)

class TelegramChannelHandler:
    def __init__(self, client: Client, channel_id: int):
        self.client = client
        self.channel_id = channel_id

    def embed_metadata(self, file_path: str, track_meta: Dict[str, Any], art_path: Optional[str]) -> bool:
        try:
            audio = mutagen.File(file_path, easy=True)
            if audio is None: raise ValueError("Mutagen could not recognize audio format.")

            audio.delete()
            if track_meta.get('title'): audio['title'] = track_meta['title']
            if track_meta.get('artist'): audio['artist'] = track_meta['artist']
            if track_meta.get('album'): audio['album'] = track_meta['album']
            if track_meta.get('date'): audio['date'] = track_meta['date']
            audio.save()

            audio_full = mutagen.File(file_path)
            if art_path and audio_full is not None:
                with open(art_path, 'rb') as art_f:
                    art_data = art_f.read()
                
                if file_path.lower().endswith('.flac'):
                    pic = FLACPicture()
                    pic.type = 3; pic.mime = 'image/jpeg'; pic.data = art_data
                    audio_full.add_picture(pic)
                elif file_path.lower().endswith('.mp3'):
                    audio_full.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=art_data))
                audio_full.save()

            logger.info(f"Successfully embedded metadata for {os.path.basename(file_path)}")
            return True
        except Exception as e:
            logger.error(f"METADATA EMBEDDING FAILED for {os.path.basename(file_path)}: {e}")
            return False

    async def upload_file(self, file_path: str, caption: str, track_meta: Dict[str, Any], thumb_path: Optional[str]) -> bool:
        file_name = os.path.basename(file_path)
        try:
            # --- THIS IS THE FIX ---
            # Set performer to an empty string to only show the title
            await self.client.send_audio(
                chat_id=self.channel_id,
                audio=file_path,
                caption=caption,
                thumb=thumb_path,
                title=track_meta.get('title', ''),
                performer="",  # <--- Hides the artist/performer name from display
                file_name=file_name
            )
            return True
        except Exception as e:
            logger.error(f"Failed to upload {file_name}: {e}")
            return False
