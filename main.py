import os
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from db import (
    init_db, add_account, get_unverified_account,
    set_channel, get_channel, add_keyword, get_all_keywords, remove_keyword,
    set_parse_interval, get_parse_interval,
    set_post_interval, get_post_interval,
    get_all_accounts, get_all_subscribers,
    add_subscription, remove_subscription, has_subscription
)
from instagram import login_account, download_media_by_url
from scheduler import start_scheduler

load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_USER_ID'))

# ─── Клавиатуры ───
def main_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🔗 Ссылка"), KeyboardButton("📩 Связь с админом")]],
        resize_keyboard=True
    )

def admin_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📊 Статус"), KeyboardButton("👥 Подписчики")],
            [KeyboardButton("➕ Выдать подписку"), KeyboardButton("➖ Убрать подписку")],
            [KeyboardButton("🔗 Ссылка"), KeyboardButton("📩 Связь с админом")],
        ],
        resize_keyboard=True
    )

def premium_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🔍 Поиск Reels"), KeyboardButton("🔗 Ссылка")],
            [KeyboardButton("📩 Связь с админом")],
        ],
        resize_keyboard=True
    )

# ─── Проверка админа ───
def is_admin(user_id):
    return user_id == ADMIN_ID

# ─── Старт ───
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    welcome_text = (
        "👋 Привет!\n\n"
        "Скинь мне ссылку на пост в Instagram — через пару секунд фото или видео будут у тебя!\n\n"
        "Я поддерживаю:\n"
        "📸 Фото\n"
        "🎬 Видео и Reels\n"
        "🖼 Карусели\n"
        "📝 Текст\n"
        "⏳ Сторис\n\n"
        "С подпиской ты можешь получить ещё больше. Напиши админу!"
    )
    
    if is_admin(user_id):
        await update.message.reply_text(welcome_text + "\n\n🔐 *Режим администратора*", parse_mode='Markdown', reply_markup=admin_keyboard())
    elif has_subscription(user_id):
        await update.message.reply_text(welcome_text + "\n\n⭐ *Премиум-доступ активен*", parse_mode='Markdown', reply_markup=premium_keyboard())
    else:
        await update.message.reply_text(welcome_text, reply_markup=main_keyboard())

# ─── Обработка кнопок и текста ───
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    
    # Кнопка "Связь с админом"
    if text == "📩 Связь с админом":
        await update.message.reply_text(
            "📩 Напиши админу: @твой_ник\n\n"
            "По вопросам подписки, сотрудничества и багов.",
            reply_markup=main_keyboard() if not is_admin(user_id) and not has_subscription(user_id) else (
                admin_keyboard() if is_admin(user_id) else premium_keyboard()
            )
        )
        return
    
    # Кнопка "Ссылка"
    if text == "🔗 Ссылка":
        await update.message.reply_text("🔗 Отправь мне ссылку на пост, Reel или сторис из Instagram:")
        return
    
    # Админ: Статус
    if text == "📊 Статус" and is_admin(user_id):
        await status_cmd(update, context)
        return
    
    # Админ: Подписчики
    if text == "👥 Подписчики" and is_admin(user_id):
        await subscribers_cmd(update, context)
        return
    
    # Админ: Выдать подписку
    if text == "➕ Выдать подписку" and is_admin(user_id):
        await update.message.reply_text("Отправь Telegram ID пользователя:")
        context.user_data['awaiting_add_sub'] = True
        return
    
    # Админ: Убрать подписку
    if text == "➖ Убрать подписку" and is_admin(user_id):
        await update.message.reply_text("Отправь Telegram ID пользователя для отключения подписки:")
        context.user_data['awaiting_remove_sub'] = True
        return
    
    # Премиум: Поиск Reels
    if text == "🔍 Поиск Reels" and (is_admin(user_id) or has_subscription(user_id)):
        keywords = get_all_keywords()
        if keywords:
            await update.message.reply_text(f"🔑 Ключевые слова: {', '.join(keywords)}\n\nОтправь ключевое слово для поиска:")
        else:
            await update.message.reply_text("⚠️ Админ ещё не настроил ключевые слова.")
        return
    
    # Обработка ссылок Instagram
    if 'instagram.com' in text:
        await update.message.reply_text("⏳ Скачиваю контент, подожди...")
        
        # Логинимся в первый доступный аккаунт
        accounts = get_all_accounts()
        client = None
        for _, acc_username, acc_password, _, is_verified in accounts:
            if is_verified:
                cl, _ = login_account(acc_username, acc_password)
                if cl:
                    client = cl
                    break
        
        if not client:
            await update.message.reply_text("❌ Сервис временно недоступен. Попробуй позже.")
            return
        
        # Пробуем скачать
        files, media_type, pk, caption, poster_username = download_media_by_url(client, text)
        
        if media_type == "photo" and files:
            with open(files[0], 'rb') as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=f"@{poster_username}\n{caption[:500]}" if caption else f"@{poster_username}"
                )
            os.remove(files[0])
        
        elif media_type == "video" and files:
            with open(files[0], 'rb') as video:
                await update.message.reply_video(
                    video=video,
                    caption=f"@{poster_username}\n{caption[:500]}" if caption else f"@{poster_username}"
                )
            os.remove(files[0])
        
        elif media_type == "carousel" and files:
            # Отправляем первый файл с подписью
            first_file = files[0]
            if first_file.endswith('.mp4'):
                with open(first_file, 'rb') as video:
                    await update.message.reply_video(
                        video=video,
                        caption=f"@{poster_username} (карусель)\n{caption[:500]}" if caption else f"@{poster_username} (карусель)"
                    )
            else:
                with open(first_file, 'rb') as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption=f"@{poster_username} (карусель)\n{caption[:500]}" if caption else f"@{poster_username} (карусель)"
                    )
            # Отправляем остальные файлы без подписи
            for f in files[1:]:
                if f.endswith('.mp4'):
                    with open(f, 'rb') as video:
                        await update.message.reply_video(video=video)
                else:
                    with open(f, 'rb') as photo:
                        await update.message.reply_photo(photo=photo)
                os.remove(f)
            os.remove(first_file)
        
        else:
            await update.message.reply_text(f"❌ Не удалось скачать. Возможно, это сторис или приватный аккаунт.\nОшибка: {caption}")
        
        return
    
    # Обработка ввода ID для выдачи подписки
    if context.user_data.get('awaiting_add_sub'):
        try:
            sub_user_id = int(text)
            add_subscription(sub_user_id, f"user_{sub_user_id}")
            await update.message.reply_text(f"✅ Подписка выдана пользователю `{sub_user_id}`", parse_mode='Markdown')
        except:
            await update.message.reply_text("❌ Отправь корректный числовой ID.")
        context.user_data['awaiting_add_sub'] = False
        return
    
    # Обработка ввода ID для удаления подписки
    if context.user_data.get('awaiting_remove_sub'):
        try:
            sub_user_id = int(text)
            remove_subscription(sub_user_id)
            await update.message.reply_text(f"✅ Подписка у пользователя `{sub_user_id}` отключена", parse_mode='Markdown')
        except:
            await update.message.reply_text("❌ Отправь корректный числовой ID.")
        context.user_data['awaiting_remove_sub'] = False
        return
    
    # Если ничего не подошло
    await update.message.reply_text(
        "Используй кнопки или отправь ссылку на Instagram.",
        reply_markup=main_keyboard() if not is_admin(user_id) and not has_subscription(user_id) else (
            admin_keyboard() if is_admin(user_id) else premium_keyboard()
        )
    )

# ─── Админские команды ───
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Нет доступа.")
        return
    
    await update.message.reply_text(
        "🔐 *Админ-панель*\n\n"
        "/add_account — Добавить Instagram аккаунт\n"
        "/verify — Верифицировать аккаунт\n"
        "/set_channel — Указать канал для постинга\n"
        "/add_keyword — Добавить ключевое слово\n"
        "/keywords — Список ключевых слов\n"
        "/remove_keyword — Удалить ключевое слово\n"
        "/set_parse — Интервал парсинга (в часах)\n"
        "/set_post — Интервал постинга (в минутах)\n"
        "/status — Текущие настройки\n"
        "/subscribers — Список подписчиков",
        parse_mode='Markdown',
        reply_markup=admin_keyboard()
    )

async def add_account_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("📝 Отправь логин и пароль через пробел:\n`логин пароль`", parse_mode='Markdown')
    context.user_data['awaiting_account'] = True

async def verify_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    
    account = get_unverified_account()
    if not account:
        await update.message.reply_text("✅ Все аккаунты верифицированы.")
        return
    
    _, username, password = account
    await update.message.reply_text(f"🔄 Вхожу в `{username}`...", parse_mode='Markdown')
    cl, error = login_account(username, password)
    
    if cl:
        await update.message.reply_text(f"✅ `{username}` верифицирован!", parse_mode='Markdown')
    elif error == "CHALLENGE_REQUIRED":
        await update.message.reply_text(f"⚠️ Нужно подтверждение для `{username}`. Зайди в приложение Instagram, подтверди вход, затем пришли код сюда.", parse_mode='Markdown')
    elif error == "VERIFICATION_CODE_REQUIRED":
        await update.message.reply_text(f"📩 Отправь код из SMS/почты для `{username}`.", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ Ошибка: {error}")

async def set_channel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("📢 Отправь username канала:\n`@мой_канал`", parse_mode='Markdown')
    context.user_data['awaiting_channel'] = True

async def add_keyword_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("🔑 Отправь ключевое слово (без #):")
    context.user_data['awaiting_keyword'] = True

async def keywords_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    keywords = get_all_keywords()
    text = "📋 Ключевые слова:\n" + "\n".join(f"• {kw}" for kw in keywords) if keywords else "Список пуст."
    await update.message.reply_text(text)

async def remove_keyword_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("🗑 Отправь ключевое слово для удаления:")
    context.user_data['awaiting_remove_keyword'] = True

async def set_parse_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("⏰ Отправь интервал парсинга в часах (минимум 1):")
    context.user_data['awaiting_parse'] = True

async def set_post_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("⏰ Отправь интервал постинга в минутах (минимум 5):")
    context.user_data['awaiting_post'] = True

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    channel = get_channel()
    keywords = get_all_keywords()
    parse_int = get_parse_interval()
    post_int = get_post_interval()
    accounts = get_all_accounts()
    
    text = "📊 **Настройки:**\n\n"
    text += f"📢 Канал: {channel or 'не настроен'}\n"
    text += f"🔍 Парсинг: каждые {parse_int} ч\n"
    text += f"📤 Постинг: каждые {post_int} мин\n"
    text += f"🔑 Ключевых слов: {len(keywords)}\n"
    text += f"👤 Аккаунтов: {len(accounts)}\n"
    
    if accounts:
        text += "\nАккаунты:\n"
        for _, username, _, _, verified in accounts:
            text += f"  {'✅' if verified else '⚠️'} {username}\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def subscribers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    subs = get_all_subscribers()
    if subs:
        text = "👥 Подписчики:\n" + "\n".join(f"• `{uid}` (@{uname})" for uid, uname in subs)
    else:
        text = "Подписчиков нет."
    await update.message.reply_text(text, parse_mode='Markdown')

# ─── Обработчик текста для админских вводов ───
async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Дополнительный обработчик для инлайн-ввода админских команд.
    Вызывается до основного handle_message.
    """
    if not is_admin(update.effective_user.id):
        return False  # не обработали, идём дальше
    
    text = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Логин/пароль
    if context.user_data.get('awaiting_account'):
        parts = text.split()
        if len(parts) == 2:
            add_account(parts[0], parts[1])
            await update.message.reply_text(f"✅ Аккаунт `{parts[0]}` добавлен. Верифицируй: /verify", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Формат: `логин пароль`", parse_mode='Markdown')
        context.user_data['awaiting_account'] = False
        return True
    
    # Код верификации
    if text.isdigit() and len(text) >= 4:
        account = get_unverified_account()
        if account:
            _, username, password = account
            await update.message.reply_text(f"🔄 Проверяю код для `{username}`...", parse_mode='Markdown')
            cl, error = login_account(username, password, verification_code=text)
            if cl:
                await update.message.reply_text(f"✅ `{username}` верифицирован!", parse_mode='Markdown')
            else:
                await update.message.reply_text(f"❌ Ошибка: {error}")
            return True
    
    # Канал
    if context.user_data.get('awaiting_channel'):
        channel = text if text.startswith('@') else f"@{text}"
        set_channel(channel)
        await update.message.reply_text(f"✅ Канал `{channel}` сохранён!", parse_mode='Markdown')
        context.user_data['awaiting_channel'] = False
        return True
    
    # Ключевое слово
    if context.user_data.get('awaiting_keyword'):
        kw = text.replace('#', '').strip()
        if add_keyword(kw):
            await update.message.reply_text(f"✅ `{kw}` добавлено!", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"⚠️ `{kw}` уже есть.", parse_mode='Markdown')
        context.user_data['awaiting_keyword'] = False
        return True
    
    # Удаление ключевого слова
    if context.user_data.get('awaiting_remove_keyword'):
        remove_keyword(text)
        await update.message.reply_text(f"🗑 `{text}` удалено.", parse_mode='Markdown')
        context.user_data['awaiting_remove_keyword'] = False
        return True
    
    # Интервал парсинга
    if context.user_data.get('awaiting_parse'):
        try:
            hours = max(1, int(text))
            set_parse_interval(hours)
            await update.message.reply_text(f"✅ Парсинг: каждые {hours} ч")
        except:
            await update.message.reply_text("❌ Отправь число.")
        context.user_data['awaiting_parse'] = False
        return True
    
    # Интервал постинга
    if context.user_data.get('awaiting_post'):
        try:
            mins = max(5, int(text))
            set_post_interval(mins)
            await update.message.reply_text(f"✅ Постинг: каждые {mins} мин")
        except:
            await update.message.reply_text("❌ Отправь число.")
        context.user_data['awaiting_post'] = False
        return True
    
    return False

# ─── Общий обработчик сообщений ───
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Сначала пробуем админские вводы
    handled = await handle_admin_input(update, context)
    if not handled:
        await handle_message(update, context)

# ─── Главная функция ───
def main():
    init_db()
    
    app = Application.builder().token(TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('admin', admin_cmd))
    app.add_handler(CommandHandler('add_account', add_account_cmd))
    app.add_handler(CommandHandler('verify', verify_cmd))
    app.add_handler(CommandHandler('set_channel', set_channel_cmd))
    app.add_handler(CommandHandler('add_keyword', add_keyword_cmd))
    app.add_handler(CommandHandler('keywords', keywords_cmd))
    app.add_handler(CommandHandler('remove_keyword', remove_keyword_cmd))
    app.add_handler(CommandHandler('set_parse', set_parse_cmd))
    app.add_handler(CommandHandler('set_post', set_post_cmd))
    app.add_handler(CommandHandler('status', status_cmd))
    app.add_handler(CommandHandler('subscribers', subscribers_cmd))
    
    # Текстовые сообщения
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    # Запуск планировщика
    start_scheduler()
    
    print("🤖 Бот запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()