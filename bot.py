#!/usr/bin/env python3
"""
Bot Main Script
Handles the main bot logic and integrates with Telegram handler using Pyrogram
"""

import os
import logging
from telegram_handler import TelegramChannelHandler
from pyrogram import Client, filters
from pyrogram.types import Message
import aiohttp
from io import BytesIO

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
api_id = os.getenv("TELEGRAM_API_ID")
api_hash = os.getenv("TELEGRAM_API_HASH")
bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
channel_id = os.getenv("TELEGRAM_CHANNEL_ID")

if not all([api_id, api_hash, bot_token, channel_id]):
    logger.error("Missing environment variables. Please check TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_BOT_TOKEN, and TELEGRAM_CHANNEL_ID.")
    exit(1)

# Initialize Telegram handler
handler = TelegramChannelHandler(api_id, api_hash, bot_token, channel_id)
logger.info("Telegram handler initialized successfully.")

# Initialize Pyrogram client
app = Client("bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Command handler for /download
@app.on_message(filters.command("download"))
async def download_command(client: Client, message: Message):
    try:
        if len(message.command) < 2:
            await message.reply("Please provide a URL after /download command. Example: /download https://example.com")
            return

        url = message.command[1]
        logger.info(f"Received download command for URL: {url}")

        # Download the file using aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    await message.reply("Failed to download the file. Check the URL.")
                    return
                file_content = await response.read()
                file_stream = BytesIO(file_content)
                file_name = url.split("/")[-1] or "downloaded_file"
                caption = f"Downloaded from {url}"

        # Upload the file using the handler
        success = await handler.upload_file(file_stream, file_name, caption)
        if success:
            await message.reply(f"Successfully uploaded {file_name} to the channel.")
        else:
            await message.reply("Failed to upload the file. Check logs for details.")
    except Exception as e:
        logger.error(f"Error in download command: {e}")
        await message.reply("An error occurred. Please try again later.")

# Start the bot with proper cleanup
if __name__ == "__main__":
    logger.info("Bot started. Listening for commands...")
    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("Stopping bot...")
        handler.stop()  # Ensure proper cleanup
    finally:
        handler.stop()  # Final cleanup
