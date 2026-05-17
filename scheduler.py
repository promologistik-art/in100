import schedule
import time
import threading
from db import (
    get_all_accounts, get_all_keywords, get_channel,
    get_parse_interval, get_post_interval,
    get_next_from_queue, mark_queued_posted,
    is_posted, mark_posted, add_to_queue, get_queue_size
)
from instagram import login_account, parse_reels, download_reel_by_pk
from telegram_poster import post_video_to_channel

def run_parser():
    """
    Парсит Reels по ключевым словам и добавляет в очередь.
    """
    print("[Парсер] Запуск поиска Reels...")
    
    keywords = get_all_keywords()
    if not keywords:
        print("[Парсер] Нет ключевых слов.")
        return
    
    accounts = get_all_accounts()
    if not accounts:
        print("[Парсер] Нет аккаунтов.")
        return
    
    client = None
    for _, username, password, _, is_verified in accounts:
        if is_verified:
            cl, error = login_account(username, password)
            if cl:
                client = cl
                break
    
    if not client:
        print("[Парсер] Нет рабочих аккаунтов.")
        return
    
    reels = parse_reels(client, keywords, amount=10)
    reels.sort(key=lambda x: x['views'], reverse=True)
    
    added = 0
    for reel in reels:
        pk = reel['pk']
        if is_posted(pk):
            continue
        
        print(f"[Парсер] Скачиваю {pk} (@{reel['username']}, {reel['views']} просмотров)")
        path = download_reel_by_pk(client, pk)
        
        if path:
            caption = f"@{reel['username']}\n{reel['caption']}\n👁 {reel['views']} | ❤ {reel['likes']} | 💬 {reel['comments']}"
            add_to_queue(pk, path, caption)
            mark_posted(pk)
            added += 1
            if added >= 5:
                break
    
    print(f"[Парсер] Добавлено в очередь: {added} Reels")

def run_poster():
    """
    Достаёт из очереди и публикует в канал.
    """
    channel_id = get_channel()
    if not channel_id:
        print("[Постер] Канал не настроен.")
        return
    
    next_item = get_next_from_queue()
    if not next_item:
        print("[Постер] Очередь пуста.")
        return
    
    queue_id, media_pk, video_path, caption = next_item
    print(f"[Постер] Публикую {media_pk}...")
    
    if post_video_to_channel(channel_id, video_path, caption):
        mark_queued_posted(queue_id)
        print(f"[Постер] Опубликовано: {media_pk}")
    else:
        print(f"[Постер] Ошибка публикации: {media_pk}")

def start_scheduler():
    """
    Запускает два планировщика: парсер и постер.
    """
    parse_hours = get_parse_interval()
    post_minutes = get_post_interval()
    
    # Парсер — раз в N часов
    schedule.every(parse_hours).hours.do(run_parser)
    
    # Постер — раз в N минут
    schedule.every(post_minutes).minutes.do(run_poster)
    
    # Первый запуск парсера через 30 секунд
    schedule.every(30).seconds.do(run_parser).tag('first_parse')
    
    def loop():
        while True:
            schedule.run_pending()
            time.sleep(1)
    
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    
    time.sleep(35)
    schedule.clear('first_parse')
    
    print(f"[Планировщик] Парсер: каждые {parse_hours} ч | Постер: каждые {post_minutes} мин")