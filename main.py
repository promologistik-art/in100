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
    keyboard = [
        [KeyboardButton("🔗 Ссылка")],
        [KeyboardButton("📩 Связь с админом")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_keyboard():
    keyboard = [
        [KeyboardButton("🔗 Ссылка"), KeyboardButton("📩 Связь с админом")],
        [KeyboardButton("📊 Статус"), KeyboardButton("👥 Подписчики")],
        [KeyboardButton("➕ Выдать подписку"), KeyboardButton("➖ Убрать подписку")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def premium_keyboard():
    keyboard = [
        [KeyboardButton("🔗 Ссылка"), KeyboardButton("🔍 Поиск Reels")],
        [KeyboardButton("📩 Связь с админом")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

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
        await update.message.reply_text(
            welcome_text + "\n\n🔐 *Режим администратора*\nИспользуй /admin для списка команд",
            parse_mode='Markdown',
            reply_markup=admin_keyboard()
        )
    elif has_subscription(user_id):
        await update.message.reply_text(
            welcome_text + "\n\n⭐ *Премиум-доступ активен*\nИспользуй /help для списка команд",
            parse_mode='Markdown',
            reply_markup=premium_keyboard()
        )
    else:
        await update.message.reply_text(welcome_text, reply_markup=main_keyboard())

# ─── Админ-панель ───
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Нет доступа.")
        return

    text = (
        "🔐 **Админ-панель**\n\n"
        "*/add_account* — добавить Instagram аккаунт\n"
        "*/verify* — верифицировать аккаунт\n"
        "*/set_channel* — целевой канал для постинга\n"
        "*/add_keyword* — добавить ключевое слово\n"
        "*/keywords* — список ключевых слов\n"
        "*/remove_keyword* — удалить ключевое слово\n"
        "*/set_parse* — интервал парсинга (часы)\n"
        "*/set_post* — интервал постинга (минуты)\n"
        "*/status* — текущие настройки\n"
        "*/subscribers* — список подписчиков"
    )
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=admin_keyboard())

# ─── Хелп для премиум ───
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id) and not has_subscription(user_id):
        await update.message.reply_text("Эта команда доступна только с премиум-подпиской.")
        return

    text = (
        "⭐ **Премиум-команды**\n\n"
        "*/search* — поиск Reels по ключевым словам\n"
        "*/set_channel* — целевой канал\n"
        "*/set_parse* — интервал парсинга\n"
        "*/set_post* — интервал постинга\n"
        "*/keywords* — список ключевых слов"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

# ─── Команды ───
async def add_account_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Только админ может добавлять аккаунты.")
        return
    await update.message.reply_text("📝 Отправь логин и пароль через пробел:\n`логин пароль`", parse_mode='Markdown')
    context.user_data['awaiting_account'] = True

async def verify_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Только админ может верифицировать аккаунты.")
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
        await update.message.reply_text(
            f"⚠️ Нужно подтверждение для `{username}`.\n"
            "Зайди в приложение Instagram, подтверди вход, затем пришли код сюда.",
            parse_mode='Markdown'
        )
    elif error == "VERIFICATION_CODE_REQUIRED":
        await update.message.reply_text(f"📩 Отправь код из SMS/почты для `{username}`.", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ Ошибка: {error}")

async def set_channel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id) and not has_subscription(user_id):
        await update.message.reply_text("⛔ Нужна премиум-подписка.")
        return
    await update.message.reply_text("📢 Отправь username канала:\n`@мой_канал`", parse_mode='Markdown')
    context.user_data['awaiting_channel'] = True

async def add_keyword_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id) and not has_subscription(user_id):
        await update.message.reply_text("⛔ Нужна премиум-подписка.")
        return
    await update.message.reply_text("🔑 Отправь ключевое слово (без #):")
    context.user_data['awaiting_keyword'] = True

async def keywords_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id) and not has_subscription(user_id):
        await update.message.reply_text("⛔ Нужна премиум-подписка.")
        return
    keywords = get_all_keywords()
    text = "📋 **Ключевые слова:**\n" + "\n".join(f"• {kw}" for kw in keywords) if keywords else "📋 Список пуст."
    await update.message.reply_text(text, parse_mode='Markdown')

async def remove_keyword_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id) and not has_subscription(user_id):
        await update.message.reply_text("⛔ Нужна премиум-подписка.")
        return
    await update.message.reply_text("🗑 Отправь ключевое слово для удаления:")
    context.user_data['awaiting_remove_keyword'] = True

async def set_parse_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id) and not has_subscription(user_id):
        await update.message.reply_text("⛔ Нужна премиум-подписка.")
        return
    await update.message.reply_text("⏰ Отправь интервал парсинга в часах (минимум 1):")
    context.user_data['awaiting_parse'] = True

async def set_post_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id) and not has_subscription(user_id):
        await update.message.reply_text("⛔ Нужна премиум-подписка.")
        return
    await update.message.reply_text("⏰ Отправь интервал постинга в минутах (минимум 5):")
    context.user_data['awaiting_post'] = True

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id) and not has_subscription(user_id):
        await update.message.reply_text("⛔ Нужна премиум-подписка.")
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

    if accounts and is_admin(user_id):
        text += "\nАккаунты:\n"
        for _, username, _, _, verified in accounts:
            text += f"  {'✅' if verified else '⚠️'} {username}\n"

    await update.message.reply_text(text, parse_mode='Markdown')

async def subscribers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Только админ может смотреть подписчиков.")
        return
    subs = get_all_subscribers()
    if subs:
        text = "👥 **Подписчики:**\n" + "\n".join(f"• `{uid}` (@{uname})" for uid, uname in subs)
    else:
        text = "Подписчиков нет."
    await update.message.reply_text(text, parse_mode='Markdown')

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id) and not has_subscription(user_id):
        await update.message.reply_text("⛔ Нужна премиум-подписка.")
        return
    keywords = get_all_keywords()
    if keywords:
        await update.message.reply_text(f"🔑 Ключевые слова: {', '.join(keywords)}\n\nОтправь ключевое слово для поиска Reels:")
        context.user_data['awaiting_search'] = True
    else:
        await update.message.reply_text("⚠️ Админ ещё не настроил ключевые слова.")

# ─── Обработка кнопок ───
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id

    kb = main_keyboard()
    if is_admin(user_id):
        kb = admin_keyboard()
    elif has_subscription(user_id):
        kb = premium_keyboard()

    # Связь с админом
    if text == "📩 Связь с админом":
        await update.message.reply_text(
            "📩 Напиши админу: @твой_ник\n\nПо вопросам подписки, сотрудничества и багов.",
            reply_markup=kb
        )
        return True

    # Ссылка
    if text == "🔗 Ссылка":
        await update.message.reply_text("🔗 Отправь мне ссылку на пост, Reel или сторис из Instagram:", reply_markup=kb)
        return True

    # Статус (админ/премиум)
    if text == "📊 Статус" and (is_admin(user_id) or has_subscription(user_id)):
        await status_cmd(update, context)
        return True

    # Подписчики (админ)
    if text == "👥 Подписчики" and is_admin(user_id):
        await subscribers_cmd(update, context)
        return True

    # Выдать подписку (админ)
    if text == "➕ Выдать подписку" and is_admin(user_id):
        await update.message.reply_text("Отправь Telegram ID пользователя для выдачи подписки:", reply_markup=kb)
        context.user_data['awaiting_add_sub'] = True
        return True

    # Убрать подписку (админ)
    if text == "➖ Убрать подписку" and is_admin(user_id):
        await update.message.reply_text("Отправь Telegram ID пользователя для отключения подписки:", reply_markup=kb)
        context.user_data['awaiting_remove_sub'] = True
        return True

    # Поиск Reels (премиум)
    if text == "🔍 Поиск Reels" and (is_admin(user_id) or has_subscription(user_id)):
        await search_cmd(update, context)
        return True

    return False

# ─── Обработка ссылок и вводов ───
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    kb = main_keyboard()
    if is_admin(user_id):
        kb = admin_keyboard()
    elif has_subscription(user_id):
        kb = premium_keyboard()

    # ── Админские вводы ──
    if is_admin(user_id):
        # Логин/пароль
        if context.user_data.get('awaiting_account'):
            parts = text.split()
            if len(parts) == 2:
                add_account(parts[0], parts[1])
                await update.message.reply_text(f"✅ Аккаунт `{parts[0]}` добавлен. Верифицируй: /verify", parse_mode='Markdown', reply_markup=kb)
            else:
                await update.message.reply_text("❌ Формат: `логин пароль`", parse_mode='Markdown', reply_markup=kb)
            context.user_data['awaiting_account'] = False
            return

        # Код верификации (цифры 4+ символов)
        if text.isdigit() and len(text) >= 4:
            account = get_unverified_account()
            if account:
                _, username, password = account
                await update.message.reply_text(f"🔄 Проверяю код для `{username}`...", parse_mode='Markdown')
                cl, error = login_account(username, password, verification_code=text)
                if cl:
                    await update.message.reply_text(f"✅ `{username}` верифицирован!", parse_mode='Markdown', reply_markup=kb)
                else:
                    await update.message.reply_text(f"❌ Ошибка: {error}", reply_markup=kb)
                return

        # Выдача подписки
        if context.user_data.get('awaiting_add_sub'):
            try:
                sub_user_id = int(text)
                add_subscription(sub_user_id, f"user_{sub_user_id}")
                await update.message.reply_text(f"✅ Подписка выдана пользователю `{sub_user_id}`", parse_mode='Markdown', reply_markup=kb)
            except:
                await update.message.reply_text("❌ Отправь корректный числовой ID.", reply_markup=kb)
            context.user_data['awaiting_add_sub'] = False
            return

        # Удаление подписки
        if context.user_data.get('awaiting_remove_sub'):
            try:
                sub_user_id = int(text)
                remove_subscription(sub_user_id)
                await update.message.reply_text(f"✅ Подписка у пользователя `{sub_user_id}` отключена", parse_mode='Markdown', reply_markup=kb)
            except:
                await update.message.reply_text("❌ Отправь корректный числовой ID.", reply_markup=kb)
            context.user_data['awaiting_remove_sub'] = False
            return

    # ── Общие вводы (админ + премиум) ──
    if is_admin(user_id) or has_subscription(user_id):
        # Канал
        if context.user_data.get('awaiting_channel'):
            channel = text if text.startswith('@') else f"@{text}"
            set_channel(channel)
            await update.message.reply_text(f"✅ Канал `{channel}` сохранён!", parse_mode='Markdown', reply_markup=kb)
            context.user_data['awaiting_channel'] = False
            return

        # Ключевое слово
        if context.user_data.get('awaiting_keyword'):
            kw = text.replace('#', '').strip().lower()
            if add_keyword(kw):
                await update.message.reply_text(f"✅ `{kw}` добавлено!", parse_mode='Markdown', reply_markup=kb)
            else:
                await update.message.reply_text(f"⚠️ `{kw}` уже есть.", parse_mode='Markdown', reply_markup=kb)
            context.user_data['awaiting_keyword'] = False
            return

        # Удаление ключевого слова
        if context.user_data.get('awaiting_remove_keyword'):
            remove_keyword(text.strip().lower())
            await update.message.reply_text(f"🗑 `{text}` удалено.", parse_mode='Markdown', reply_markup=kb)
            context.user_data['awaiting_remove_keyword'] = False
            return

        # Интервал парсинга
        if context.user_data.get('awaiting_parse'):
            try:
                hours = max(1, int(text))
                set_parse_interval(hours)
                await update.message.reply_text(f"✅ Парсинг: каждые {hours} ч", reply_markup=kb)
            except:
                await update.message.reply_text("❌ Отправь число.", reply_markup=kb)
            context.user_data['awaiting_parse'] = False
            return

        # Интервал постинга
        if context.user_data.get('awaiting_post'):
            try:
                mins = max(5, int(text))
                set_post_interval(mins)
                await update.message.reply_text(f"✅ Постинг: каждые {mins} мин", reply_markup=kb)
            except:
                await update.message.reply_text("❌ Отправь число.", reply_markup=kb)
            context.user_data['awaiting_post'] = False
            return

        # Поиск Reels
        if context.user_data.get('awaiting_search'):
            await update.message.reply_text(f"🔍 Ищу Reels по запросу: `{text}`...", parse_mode='Markdown')
            from instagram import parse_reels, download_reel_by_pk
            accounts = get_all_accounts()
            client = None
            for _, uname, pwd, _, verified in accounts:
                if verified:
                    cl, _ = login_account(uname, pwd)
                    if cl:
                        client = cl
                        break
            if not client:
                await update.message.reply_text("❌ Сервис недоступен.", reply_markup=kb)
                context.user_data['awaiting_search'] = False
                return

            reels = parse_reels(client, [text], amount=5)
            if not reels:
                await update.message.reply_text("😕 Ничего не найдено.", reply_markup=kb)
            else:
                for reel in reels[:3]:
                    await update.message.reply_text(f"⏳ Скачиваю: {reel['url']}")
                    path = download_reel_by_pk(client, reel['pk'])
                    if path:
                        cap = f"@{reel['username']}\n{reel['caption']}\n👁 {reel['views']} | ❤ {reel['likes']}"
                        with open(path, 'rb') as vid:
                            await update.message.reply_video(video=vid, caption=cap[:1024])
                        os.remove(path)
                    else:
                        await update.message.reply_text(f"❌ Не удалось скачать {reel['url']}")
            context.user_data['awaiting_search'] = False
            return

    # ── Ссылка на Instagram ──
    if 'instagram.com' in text:
        await update.message.reply_text("⏳ Скачиваю контент, подожди...")

        accounts = get_all_accounts()
        client = None
        for _, uname, pwd, _, verified in accounts:
            if verified:
                cl, _ = login_account(uname, pwd)
                if cl:
                    client = cl
                    break

        if not client:
            await update.message.reply_text(
                "❌ Сервис временно недоступен. Админ ещё не настроил Instagram-аккаунт.\n"
                "Попробуй позже или напиши админу.",
                reply_markup=kb
            )
            return

        files, media_type, pk, caption, poster_username = download_media_by_url(client, text)

        caption_text = f"@{poster_username}\n{caption[:500]}" if caption else f"@{poster_username}"

        if media_type == "photo" and files:
            with open(files[0], 'rb') as photo:
                await update.message.reply_photo(photo=photo, caption=caption_text, reply_markup=kb)
            os.remove(files[0])

        elif media_type == "video" and files:
            with open(files[0], 'rb') as video:
                await update.message.reply_video(video=video, caption=caption_text, reply_markup=kb)
            os.remove(files[0])

        elif media_type == "carousel" and files:
            first = files[0]
            if first.endswith('.mp4'):
                with open(first, 'rb') as v:
                    await update.message.reply_video(video=v, caption=f"{caption_text} (карусель)", reply_markup=kb)
            else:
                with open(first, 'rb') as p:
                    await update.message.reply_photo(photo=p, caption=f"{caption_text} (карусель)", reply_markup=kb)
            os.remove(first)
            for f in files[1:]:
                if f.endswith('.mp4'):
                    with open(f, 'rb') as v:
                        await update.message.reply_video(video=v)
                else:
                    with open(f, 'rb') as p:
                        await update.message.reply_photo(photo=p)
                os.remove(f)

        else:
            await update.message.reply_text(
                f"❌ Не удалось скачать. Возможно, аккаунт приватный или ссылка недоступна.\nОшибка: {caption}",
                reply_markup=kb
            )
        return

    # ── Ничего не подошло ──
    await update.message.reply_text(
        "Используй кнопки или отправь ссылку на Instagram.",
        reply_markup=kb
    )

# ─── Главный обработчик сообщений ───
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Сначала обрабатываем кнопки
    button_handled = await handle_buttons(update, context)
    if not button_handled:
        await handle_text(update, context)

# ─── main ───
def main():
    init_db()

    app = Application.builder().token(TOKEN).build()

    # Команды
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('admin', admin_cmd))
    app.add_handler(CommandHandler('help', help_cmd))
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
    app.add_handler(CommandHandler('search', search_cmd))

    # Все текстовые сообщения
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Планировщик
    start_scheduler()

    print("🤖 Бот запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()