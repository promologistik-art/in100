import os
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))

def post_video_to_channel(channel_id, video_path, caption=""):
    """
    Отправляет видео в Telegram-канал.
    Возвращает True если успешно.
    """
    try:
        with open(video_path, 'rb') as video:
            bot.send_video(
                chat_id=channel_id,
                video=video,
                caption=caption[:1024],  # Лимит Telegram
                supports_streaming=True
            )
        # Удаляем файл после отправки
        if os.path.exists(video_path):
            os.remove(video_path)
        return True
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")
        return False