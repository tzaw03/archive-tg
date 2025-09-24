import os
import asyncio
import logging
from typing import Optional, Dict, Any

from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeAudio
from telethon.errors import FloodWaitError

import mutagen
from mutagen.flac import Picture as FLACPicture
from mutagen.id3 import APIC, ID3, error as ID3Error

logger = logging.getLogger(__name__)

class TelegramChannelHandler:
    def __init__(self, client: TelegramClient, channel_id: int):
        self.client = client
        self.channel_id = channel_id

    def embed_metadata(self, file_path: str, track_meta: Dict[str, Any], art_path: Optional[str]) -> bool:
        """Embeds metadata + album art into audio file on disk."""
        try:
            audio = mutagen.File(file_path, easy=True)
            if audio is None:
                raise ValueError("Unrecognized audio format.")

            # Write basic tags (without deleting technical metadata)
            if track_meta.get('title'): audio['title'] = track_meta['title']
            if track_meta.get('artist'): audio['artist'] = track_meta['artist']
            if track_meta.get('album'): audio['album'] = track_meta['album']
            if track_meta.get('date'): audio['date'] = track_meta['date']
            audio.save()

            # Reload full object for album art embedding
            audio_full = mutagen.File(file_path)
            if art_path and audio_full is not None:
                with open(art_path, 'rb') as art_f:
                    art_data = art_f.read()

                file_name_lower = file_path.lower()
                if file_name_lower.endswith('.flac'):
                    pic = FLACPicture()
                    pic.type = 3
                    pic.mime = 'image/jpeg'
                    pic.desc = 'Cover'
                    pic.data = art_data
                    audio_full.add_picture(pic)
                elif file_name_lower.endswith('.mp3'):
                    if audio_full.tags is None:
                        audio_full.add_tags()
                    audio_full.tags.add(
                        APIC(
                            encoding=3,
                            mime='image/jpeg',
                            type=3,
                            desc='Cover',
                            data=art_data
                        )
                    )
                audio_full.save()

            logger.info(f"✅ Metadata embedded for {os.path.basename(file_path)}")
            return True

        except Exception as e:
            logger.error(f"❌ Metadata embedding failed for {os.path.basename(file_path)}: {e}")
            return False

    async def upload_file(self, file_path: str, caption: str, track_meta: Dict[str, Any]) -> bool:
        """Uploads a file from disk to Telegram with proper attributes."""
        file_name = os.path.basename(file_path)
        try:
            attributes = []
            duration = 0
            try:
                audio = mutagen.File(file_path)
                if audio and audio.info and hasattr(audio.info, "length"):
                    duration = int(audio.info.length)
            except Exception:
                pass

            if file_name.lower().endswith(('.mp3', '.flac', '.wav', '.ogg')):
                attributes.append(DocumentAttributeAudio(
                    duration=duration,
                    title=track_meta.get('title', file_name),
                    performer=track_meta.get('artist', "Unknown Artist")
                ))

            await self.client.send_file(
                self.channel_id,
                file=file_path,
                caption=caption,
                attributes=attributes,
                force_document=False,
                supports_streaming=True
            )
            return True

        except FloodWaitError as e:
            logger.warning(f"⚠️ FloodWait: Sleeping {e.seconds}s...")
            await asyncio.sleep(e.seconds)
            return await self.upload_file(file_path, caption, track_meta)
        except Exception as e:
            logger.error(f"❌ Failed to upload {file_name}: {e}")
            return False
