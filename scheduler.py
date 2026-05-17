import schedule
import time
import threading
from db import (
    get_all_accounts, get_all_keywords, get_channel,
    get_schedule, get_pending_links, mark_link_processed,
    is_posted, mark_posted
)
from instagram import login_account, parse_reels, download_reel_by_pk, download_reel_by_url
from telegram_poster import post_video_to_channel

def run_parser():
    """
    Основная функция парсинга и постинга.
    """
    print("[Парсер] Запуск...")
    
    channel_id = get_channel()
    if not channel_id:
        print("[Парсер] Канал не настроен. Пропускаю.")
        return
    
    keywords = get_all_keywords()
    pending_links = get_pending_links()
    
    if not keywords and not pending_links:
        print("[Парсер] Нет ключевых слов и ссылок. Пропускаю.")
        return
    
    accounts = get_all_accounts()
    if not accounts:
        print("[Парсер] Нет аккаунтов. Пропускаю.")
        return
    
    # Берём первый верифицированный аккаунт
    client = None
    for acc_id, username, password, session_json, is_verified in accounts:
        if is_verified:
            cl, error = login_account(username, password)
            if cl:
                client = cl
                break
    
    if not client:
        print("[Парсер] Нет рабочих аккаунтов. Пропускаю.")
        return
    
    # 1. Обрабатываем очередь ссылок
    for link_id, url in pending_links:
        print(f"[Парсер] Скачиваю по ссылке: {url}")
        path, media_pk = download_reel_by_url(client, url)
        if path and media_pk:
            if not is_posted(str(media_pk)):
                if post_video_to_channel(channel_id, path):
                    mark_posted(str(media_pk))
                    mark_link_processed(link_id, 'posted')
                    print(f"[Парсер] Опубликовано: {url}")
            else:
                mark_link_processed(link_id, 'duplicate')
        else:
            mark_link_processed(link_id, 'error')
    
    # 2. Парсим по ключевым словам
    if keywords:
        reels = parse_reels(client, keywords, amount=10)
        
        # Сортируем по просмотрам
        reels.sort(key=lambda x: x['views'], reverse=True)
        
        posted_count = 0
        for reel in reels:
            if posted_count >= 3:  # Не больше 3 за один запуск
                break
            
            pk = reel['pk']
            if is_posted(pk):
                continue
            
            print(f"[Парсер] Скачиваю Reel {pk} (@{reel['username']}, {reel['views']} просмотров)")
            path = download_reel_by_pk(client, pk)
            
            if path:
                caption = f"@{reel['username']}\n{reel['caption']}\n\n👁 {reel['views']} | ❤ {reel['likes']} | 💬 {reel['comments']}"
                if post_video_to_channel(channel_id, path, caption):
                    mark_posted(pk)
                    posted_count += 1
                    print(f"[Парсер] Опубликовано: {reel['url']}")
    
    print("[Парсер] Завершён.")

def start_scheduler():
    """
    Запускает планировщик в отдельном потоке.
    """
    hours = get_schedule()
    schedule.every(hours).hours.do(run_parser)
    
    # Первый запуск через 10 секунд после старта
    schedule.every(10).seconds.do(run_parser).tag('first_run')
    
    def loop():
        while True:
            schedule.run_pending()
            time.sleep(1)
    
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    
    # Убираем первый запуск после выполнения
    time.sleep(15)
    schedule.clear('first_run')
    
    print(f"[Планировщик] Запущен. Интервал: {hours} часа(ов)")