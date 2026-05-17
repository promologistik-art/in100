import os
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()
bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))

def post_video_to_channel(channel_id, video_path, caption=""):
    try:
        with open(video_path, 'rb') as video:
            bot.send_video(
                chat_id=channel_id,
                video=video,
                caption=caption[:1024],
                supports_streaming=True
            )
        if os.path.exists(video_path):
            os.remove(video_path)
        return True
    except Exception as e:
        print(f"Ошибка отправки в канал: {e}")
        return False

def post_photo_to_channel(channel_id, photo_path, caption=""):
    try:
        with open(photo_path, 'rb') as photo:
            bot.send_photo(
                chat_id=channel_id,
                photo=photo,
                caption=caption[:1024]
            )
        if os.path.exists(photo_path):
            os.remove(photo_path)
        return True
    except Exception as e:
        print(f"Ошибка отправки фото в канал: {e}")
        return False