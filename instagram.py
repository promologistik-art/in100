import os
import tempfile
from instagrapi import Client
from db import save_session, load_session

DOWNLOAD_FOLDER = "downloads"

def ensure_download_folder():
    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER)

def login_account(username, password, verification_code=None):
    cl = Client()
    
    session_json = load_session(username)
    if session_json:
        try:
            cl.load_settings(session_json)
            cl.login(username, password)
            return cl, None
        except:
            pass
    
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

def download_media_by_url(client, url):
    """
    Универсальная функция: скачивает фото/видео/карусель/сторис по ссылке.
    Возвращает: список путей к файлам, тип контента, media_pk, caption
    """
    ensure_download_folder()
    
    try:
        media_pk = client.media_pk_from_url(url)
        media_info = client.media_info(media_pk)
        media_type = media_info.media_type
        caption = media_info.caption_text[:1000] if media_info.caption_text else ""
        username = media_info.user.username
        
        files = []
        
        # Тип 1 — фото
        if media_type == 1:
            path = client.photo_download(media_pk, folder=DOWNLOAD_FOLDER)
            files.append(path)
            return files, "photo", str(media_pk), caption, username
        
        # Тип 2 — видео (Reels, обычные видео)
        elif media_type == 2:
            path = client.video_download(media_pk, folder=DOWNLOAD_FOLDER)
            files.append(path)
            return files, "video", str(media_pk), caption, username
        
        # Тип 8 — карусель (несколько фото/видео)
        elif media_type == 8:
            for resource in media_info.resources:
                if resource.media_type == 1:  # фото в карусели
                    path = client.photo_download(resource.pk, folder=DOWNLOAD_FOLDER)
                    files.append(path)
                elif resource.media_type == 2:  # видео в карусели
                    path = client.video_download(resource.pk, folder=DOWNLOAD_FOLDER)
                    files.append(path)
            return files, "carousel", str(media_pk), caption, username
        
        else:
            return None, "unknown", str(media_pk), "", ""
    
    except Exception as e:
        return None, "error", "", str(e), ""

def download_story_by_url(client, url):
    """
    Скачивает сторис по ссылке.
    """
    ensure_download_folder()
    try:
        story_pk = client.story_pk_from_url(url)
        path = client.story_download(story_pk, folder=DOWNLOAD_FOLDER)
        return path, str(story_pk)
    except Exception as e:
        return None, str(e)

def parse_reels(client, keywords, amount=10):
    """
    Ищет Reels по ключевым словам.
    """
    reels = []
    ensure_download_folder()
    
    for keyword in keywords:
        try:
            medias = client.hashtag_medias_top(keyword, amount=amount // len(keywords) + 1)
            
            for media in medias:
                if media.media_type == 2:
                    pk = str(media.pk)
                    reels.append({
                        'pk': pk,
                        'code': media.code,
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

def download_reel_by_pk(client, pk):
    ensure_download_folder()
    try:
        path = client.video_download(int(pk), folder=DOWNLOAD_FOLDER)
        return path
    except Exception as e:
        print(f"Ошибка скачивания {pk}: {e}")
        return None