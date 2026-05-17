import sqlite3

DB_PATH = "bot_data.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Аккаунты Instagram для парсинга
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
    
    # Целевой канал для постинга
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS target_channel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Ключевые слова для поиска
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL UNIQUE
        )
    ''')
    
    # Интервал парсинга (в часах)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parse_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interval_hours INTEGER NOT NULL DEFAULT 3
        )
    ''')
    
    # Интервал постинга (в минутах)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS post_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interval_minutes INTEGER NOT NULL DEFAULT 30
        )
    ''')
    
    # Опубликованные медиа (чтобы не дублировать)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posted_media (
            media_pk TEXT PRIMARY KEY,
            posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Подписки пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            is_active INTEGER DEFAULT 1,
            granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        )
    ''')
    
    # Очередь на публикацию (найденные Reels ждут своего времени)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS post_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_pk TEXT NOT NULL,
            video_path TEXT NOT NULL,
            caption TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending'
        )
    ''')
    
    conn.commit()
    conn.close()

# ─── Аккаунты ───
def add_account(username, password):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO accounts (username, password) VALUES (?, ?)", (username, password))
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
    cursor.execute("UPDATE accounts SET session_json = ?, is_verified = 1 WHERE username = ?", (session_json, username))
    conn.commit()
    conn.close()

def load_session(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT session_json FROM accounts WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else None

# ─── Канал ───
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

# ─── Ключевые слова ───
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

# ─── Расписание парсинга ───
def set_parse_interval(hours):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM parse_schedule")
    cursor.execute("INSERT INTO parse_schedule (interval_hours) VALUES (?)", (hours,))
    conn.commit()
    conn.close()

def get_parse_interval():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT interval_hours FROM parse_schedule LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 3

# ─── Расписание постинга ───
def set_post_interval(minutes):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM post_schedule")
    cursor.execute("INSERT INTO post_schedule (interval_minutes) VALUES (?)", (minutes,))
    conn.commit()
    conn.close()

def get_post_interval():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT interval_minutes FROM post_schedule LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 30

# ─── Опубликованные ───
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

# ─── Подписки ───
def add_subscription(user_id, username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO subscriptions (user_id, username, is_active) VALUES (?, ?, 1)", (user_id, username))
    conn.commit()
    conn.close()

def remove_subscription(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE subscriptions SET is_active = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def has_subscription(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM subscriptions WHERE user_id = ? AND is_active = 1", (user_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def get_all_subscribers():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username FROM subscriptions WHERE is_active = 1")
    rows = cursor.fetchall()
    conn.close()
    return rows

# ─── Очередь постинга ───
def add_to_queue(media_pk, video_path, caption=""):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO post_queue (media_pk, video_path, caption) VALUES (?, ?, ?)", (media_pk, video_path, caption))
    conn.commit()
    conn.close()

def get_next_from_queue():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, media_pk, video_path, caption FROM post_queue WHERE status = 'pending' ORDER BY added_at ASC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row

def mark_queued_posted(queue_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE post_queue SET status = 'posted' WHERE id = ?", (queue_id,))
    conn.commit()
    conn.close()

def get_queue_size():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM post_queue WHERE status = 'pending'")
    count = cursor.fetchone()[0]
    conn.close()
    return count