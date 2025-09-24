import os
import logging

# 1. Logging ကို အရင်ဆုံး setup လုပ်ပါ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info("--- DIAGNOSTIC SCRIPT STARTING ---")

try:
    # 2. Environment Variables အားလုံးကို ဖတ်ကြည့်ပါ
    api_id_str = os.environ.get('TELEGRAM_API_ID')
    api_hash_str = os.environ.get('TELEGRAM_API_HASH')
    bot_token_str = os.environ.get('TELEGRAM_BOT_TOKEN')
    channel_id_str = os.environ.get('TELEGRAM_CHANNEL_ID')

    # 3. Variables တွေရဲ့ အခြေအနေကို (secret တွေမဖော်ပြဘဲ) log ထုတ်ကြည့်ပါ
    logger.info(f"API_ID Found: {bool(api_id_str)}, Length: {len(api_id_str) if api_id_str else 0}, First 4 Chars: {api_id_str[:4] if api_id_str else 'N/A'}")
    logger.info(f"API_HASH Found: {bool(api_hash_str)}, Length: {len(api_hash_str) if api_hash_str else 0}, First 4 Chars: {api_hash_str[:4] if api_hash_str else 'N/A'}")
    logger.info(f"BOT_TOKEN Found: {bool(bot_token_str)}, Length: {len(bot_token_str) if bot_token_str else 0}, First 10 Chars: {bot_token_str[:10] if bot_token_str else 'N/A'}")
    logger.info(f"CHANNEL_ID Found: {bool(channel_id_str)}, Length: {len(channel_id_str) if channel_id_str else 0}, Value: {channel_id_str if channel_id_str else 'N/A'}")

    # 4. အရေးအကြီးဆုံးဖြစ်တဲ့ API_ID ကို integer ပြောင်းလို့ရမရ စစ်ဆေးပါ
    if api_id_str:
        logger.info("Attempting to convert API_ID to integer...")
        api_id_int = int(api_id_str)
        logger.info(f"SUCCESS: API_ID converted to integer: {api_id_int}")
    else:
        logger.warning("API_ID is not set or empty.")

    logger.info("--- DIAGNOSTIC SCRIPT FINISHED SUCCESSFULLY ---")

except Exception as e:
    # error တစ်ခုခုတက်ရင် log မှာ အကြောင်းစုံဖော်ပြခိုင်းပါ
    logger.error("--- DIAGNOSTIC SCRIPT FAILED WITH AN ERROR ---", exc_info=True)
