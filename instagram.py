import os
from instagrapi import Client
from db import save_session, load_session, is_posted, mark_posted

DOWNLOAD_FOLDER = "downloads"

def ensure_download_folder():
    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER)

def login_account(username, password, verification_code=None):
    """
    Логин в Instagram. Если нужен код — возвращает запрос на верификацию.
    """
    cl = Client()
    
    # Пробуем загрузить сессию
    session_json = load_session(username)
    if session_json:
        try:
            cl.load_settings(session_json)
            cl.login(username, password)
            return cl, None  # Успешно залогинились
        except:
            pass
    
    # Сессии нет или просрочена — логинимся заново
    try:
        cl.login(username, password, verification_code=verification_code)
        session_json = cl.dump_settings()
        save_session(username, session_json)
        return cl, None
    except Exception as e:
        error_msg = str(e)
        if "checkpoint" in error_msg.lower() or "challenge" in error_msg.lower():
            return None, "CHALLENGE_REQUIRED"
        elif "verification" in error_msg.lower() or "code" in error_msg.lower():
            return None, "VERIFICATION_CODE_REQUIRED"
        else:
            return None, error_msg

def parse_reels(client, keywords, amount=10):
    """
    Ищет Reels по ключевым словам и возвращает список с метриками.
    """
    reels = []
    ensure_download_folder()
    
    for keyword in keywords:
        try:
            medias = client.hashtag_medias_top(keyword, amount=amount // len(keywords) + 1)
            
            for media in medias:
                if media.media_type == 2:  # Только Reels
                    pk = str(media.pk)
                    if not is_posted(pk):
                        reels.append({
                            'pk': pk,
                            'url': f"https://www.instagram.com/reel/{media.code}/",
                            'caption': media.caption_text[:200] if media.caption_text else "",
                            'views': media.view_count or 0,
                            'likes': media.like_count or 0,
                            'comments': media.comment_count or 0,
                            'username': media.user.username,
                        })
        except Exception as e:
            print(f"Ошибка парсинга по {keyword}: {e}")
            continue
    
    return reels

def download_reel_by_url(client, url):
    """
    Скачивает Reel по прямой ссылке.
    """
    ensure_download_folder()
    try:
        media_pk = client.media_pk_from_url(url)
        path = client.video_download(media_pk, folder=DOWNLOAD_FOLDER)
        return path, media_pk
    except Exception as e:
        return None, str(e)

def download_reel_by_pk(client, pk):
    """
    Скачивает Reel по media_pk.
    """
    ensure_download_folder()
    try:
        path = client.video_download(int(pk), folder=DOWNLOAD_FOLDER)
        return path
    except Exception as e:
        print(f"Ошибка скачивания {pk}: {e}")
        return None