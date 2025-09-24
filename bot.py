import os
import logging
import asyncio
import shutil
from typing import Dict, Any

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from archive_handler import ArchiveOrgHandler
from telegram_handler import TelegramChannelHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Environment Variables ---
API_ID = int(os.environ.get('TELEGRAM_API_ID', '0'))
API_HASH = os.environ.get('TELEGRAM_API_HASH', '')
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHANNEL_ID = int(os.environ.get('TELEGRAM_CHANNEL_ID', '0'))

app = Client("archive_bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

archive_handler = ArchiveOrgHandler()
channel_handler = TelegramChannelHandler(app, CHANNEL_ID)
user_sessions: Dict[str, Dict[str, Any]] = {}

@app.on_message(filters.command(["start", "help"]))
async def handle_start(client, message):
    await message.reply_text("Welcome! Use /download [URL] to start.", quote=True)

@app.on_message(filters.command("download"))
async def handle_download(client, message):
    user_id = message.from_user.id
    try:
        url = message.text.split(' ', 1)[1].strip()
    except IndexError:
        await message.reply_text("Please provide a valid archive.org URL.", quote=True)
        return
    
    status_msg = await message.reply_text("🔍 Fetching metadata...", quote=True)
    metadata = await archive_handler.get_metadata(url)
    if not metadata:
        await status_msg.edit_text("❌ Could not fetch metadata.")
        return

    session_key = f"{user_id}_{message.id}"
    user_sessions[session_key] = {'metadata': metadata}
    formats = archive_handler.get_available_formats(metadata)
    if not formats:
        await status_msg.edit_text("❌ No downloadable formats found.")
        return

    buttons = [
        [InlineKeyboardButton(f"{name} ({len(files)} files)", f"format_{name}_{session_key}")]
        for name, files in formats.items()
    ]
    buttons.append([InlineKeyboardButton("✖️ Cancel", f"cancel_{session_key}")])
    keyboard = InlineKeyboardMarkup(buttons)
    
    item_title = metadata.get('metadata', {}).get('title', 'Unknown Item')
    await status_msg.edit_text(f"**{item_title}**\n\nPlease select a format:", reply_markup=keyboard)

@app.on_callback_query()
async def handle_button_press(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if data.startswith('format_'):
        _, format_name, session_key = data.split('_', 2)
        
        session = user_sessions.get(session_key)
        if not session:
            await callback_query.answer("⚠️ Session expired.", show_alert=True)
            return

        await callback_query.edit_message_text(f"✅ Format '{format_name}' selected. Processing...")
        asyncio.create_task(process_album_download(session, format_name, user_id, session_key))
    
    elif data.startswith('cancel_'):
        session_key = data.replace('cancel_', '')
        if session_key in user_sessions:
            del user_sessions[session_key]
        await callback_query.edit_message_text("Operation cancelled.")


async def process_album_download(session: dict, format_name: str, user_id: int, session_key: str):
    temp_dir = f"/tmp/archive_bot_{user_id}_{format_name.replace(' ', '_')}"
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        metadata = session['metadata']
        formats = archive_handler.get_available_formats(metadata)
        files_to_process = formats.get(format_name, [])
        status_msg_to_user = await app.send_message(user_id, "🎨 Downloading album art...")
        
        art_path = await archive_handler.get_album_art_to_disk(metadata, temp_dir)

        album_meta = metadata.get('metadata', {})
        album_title = album_meta.get('title', 'Unknown Album')
        album_year = album_meta.get('date', album_meta.get('year', ''))
        
        # --- FIX #3: ADDING EMOJIS ---
        caption = (f"📀 **Album:** {album_title}\n"
                   f"🗓️ **Year:** {album_year}\n"
                   f"🎧 **Format:** {format_name}")
        
        if art_path:
            await app.send_photo(chat_id=CHANNEL_ID, photo=art_path, caption=caption)
        else:
            await app.send_message(chat_id=CHANNEL_ID, text=caption)

        total_files = len(files_to_process)
        for i, file_info in enumerate(files_to_process, 1):
            file_name = file_info['name']
            identifier = file_info['identifier']
            
            await status_msg_to_user.edit_text(f"Downloading {i}/{total_files}:\n`{file_name}`")
            track_path = await archive_handler.download_file_to_disk(identifier, file_name, temp_dir)
            if not track_path: continue

            await status_msg_to_user.edit_text(f"Embedding metadata for {i}/{total_files}...")
            
            # --- FIX #1: CORRECT ARTIST NAME ---
            # Prioritize 'artist' field, fallback to 'creator'
            artist_name = album_meta.get('artist', album_meta.get('creator', 'Unknown Artist'))
            
            track_meta = {
                'title': os.path.splitext(file_name)[0].replace('_', ' ').strip(),
                'artist': artist_name, 
                'album': album_title, 
                'date': album_year
            }
            embed_success = channel_handler.embed_metadata(track_path, track_meta, art_path)
            
            await status_msg_to_user.edit_text(f"Uploading {i}/{total_files}:\n`{file_name}`")
            if not embed_success:
                await app.send_message(user_id, f"⚠️ Metadata embedding failed for `{file_name}`.")
            
            # --- FIX #2: REMOVE REDUNDANT CAPTION ---
            # Pass an empty string "" as caption for audio files
            await channel_handler.upload_file(track_path, "", track_meta, art_path)

        await status_msg_to_user.edit_text(f"✅ **Process Complete!** All {total_files} tracks uploaded.")
    except Exception as e:
        logger.error(f"A critical error occurred: {e}", exc_info=True)
        await app.send_message(user_id, f"❌ A critical error occurred: {e}")
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")
        if session_key in user_sessions:
            del user_sessions[session_key]
        
if __name__ == "__main__":
    logger.info("Bot starting...")
    app.run()
