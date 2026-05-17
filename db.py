import sqlite3
import os

DB_PATH = "bot_data.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            session_json TEXT,
            is_verified INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS target_channel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL UNIQUE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interval_hours INTEGER NOT NULL DEFAULT 3
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posted_media (
            media_pk TEXT PRIMARY KEY,
            posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# Функции для работы с аккаунтами
def add_account(username, password):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO accounts (username, password) VALUES (?, ?)",
        (username, password)
    )
    conn.commit()
    conn.close()

def get_all_accounts():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password, session_json, is_verified FROM accounts")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_unverified_account():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password FROM accounts WHERE is_verified = 0 LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row

def save_session(username, session_json):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE accounts SET session_json = ?, is_verified = 1 WHERE username = ?",
        (session_json, username)
    )
    conn.commit()
    conn.close()

def load_session(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT session_json FROM accounts WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else None

# Функции для канала
def set_channel(channel_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM target_channel")
    cursor.execute("INSERT INTO target_channel (channel_id) VALUES (?)", (channel_id,))
    conn.commit()
    conn.close()

def get_channel():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id FROM target_channel LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

# Функции для ключевых слов
def add_keyword(keyword):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO keywords (keyword) VALUES (?)", (keyword,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_all_keywords():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT keyword FROM keywords")
    rows = [row[0] for row in cursor.fetchall()]
    conn.close()
    return rows

def remove_keyword(keyword):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM keywords WHERE keyword = ?", (keyword,))
    conn.commit()
    conn.close()

# Функции для расписания
def set_schedule(hours):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM schedule")
    cursor.execute("INSERT INTO schedule (interval_hours) VALUES (?)", (hours,))
    conn.commit()
    conn.close()

def get_schedule():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT interval_hours FROM schedule LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 3

# Функции для проверки опубликованных
def is_posted(media_pk):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM posted_media WHERE media_pk = ?", (media_pk,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def mark_posted(media_pk):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO posted_media (media_pk) VALUES (?)", (media_pk,))
    conn.commit()
    conn.close()

# Функции для очереди ссылок
def add_pending_link(url):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO pending_links (url) VALUES (?)", (url,))
    conn.commit()
    conn.close()

def get_pending_links():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, url FROM pending_links WHERE status = 'pending'")
    rows = cursor.fetchall()
    conn.close()
    return rows

def mark_link_processed(link_id, status='downloaded'):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE pending_links SET status = ? WHERE id = ?", (status, link_id))
    conn.commit()
    conn.close()