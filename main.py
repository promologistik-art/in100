import os
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from db import (
    init_db, add_account, get_unverified_account, save_session,
    set_channel, get_channel, add_keyword, get_all_keywords, remove_keyword,
    set_schedule, get_schedule, get_all_accounts, add_pending_link
)
from instagram import login_account
from scheduler import start_scheduler, run_parser

load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_USER_ID'))

# Проверка на админа
def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("⛔ У вас нет доступа к этому боту.")
            return
        return await func(update, context)
    return wrapper

# Команда /start
@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я бот для парсинга Instagram Reels.\n\n"
        "Доступные команды:\n"
        "/add_account — Добавить Instagram аккаунт\n"
        "/verify — Пройти верификацию аккаунта\n"
        "/set_channel — Указать канал для публикации\n"
        "/add_keyword — Добавить ключевое слово\n"
        "/keywords — Список ключевых слов\n"
        "/remove_keyword — Удалить ключевое слово\n"
        "/set_schedule — Настроить расписание (в часах)\n"
        "/add_link — Добавить ссылку на Reel\n"
        "/status — Текущие настройки\n"
        "/parse — Запустить парсинг вручную\n"
    )

# Команда /add_account
@admin_only
async def add_account_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 Отправь логин и пароль в формате:\n"
        "`логин пароль`\n\n"
        "Пример: `myaccount mypassword123`",
        parse_mode='Markdown'
    )

# Обработчик текста (логин/пароль)
@admin_only
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    parts = text.split()
    
    # Если это логин и пароль (2 слова)
    if len(parts) == 2 and not text.startswith('/'):
        username, password = parts
        add_account(username, password)
        await update.message.reply_text(
            f"✅ Аккаунт `{username}` добавлен!\n"
            "Теперь пройди верификацию: /verify",
            parse_mode='Markdown'
        )
        return
    
    await update.message.reply_text("❌ Неизвестный формат. Используй команды из /start")

# Команда /verify
@admin_only
async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account = get_unverified_account()
    if not account:
        await update.message.reply_text("✅ Все аккаунты верифицированы или аккаунтов нет.")
        return
    
    acc_id, username, password = account
    await update.message.reply_text(f"🔄 Пробую войти в `{username}`...", parse_mode='Markdown')
    
    cl, error = login_account(username, password)
    
    if cl:
        await update.message.reply_text(f"✅ Аккаунт `{username}` верифицирован!")
    elif error == "CHALLENGE_REQUIRED":
        await update.message.reply_text(
            f"⚠️ Instagram требует подтверждение для `{username}`.\n"
            "Зайди в приложение Instagram, подтверди вход, затем пришли код сюда:\n"
            "`код_верификации`",
            parse_mode='Markdown'
        )
    elif error == "VERIFICATION_CODE_REQUIRED":
        await update.message.reply_text(
            f"📩 Instagram отправил код для `{username}`.\n"
            "Пришли его сюда в формате:\n"
            "`код`",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(f"❌ Ошибка: {error}")

# Команда /set_channel
@admin_only
async def set_channel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📢 Отправь username канала (с @ или без):\n"
        "Пример: `@my_channel` или `my_channel`"
    )
    context.user_data['awaiting_channel'] = True

# Команда /add_keyword
@admin_only
async def add_keyword_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔑 Отправь ключевое слово (без #):\n"
        "Пример: `trending`"
    )
    context.user_data['awaiting_keyword'] = True

# Команда /keywords
@admin_only
async def keywords_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keywords = get_all_keywords()
    if keywords:
        text = "📋 Ключевые слова:\n" + "\n".join(f"• {kw}" for kw in keywords)
    else:
        text = "📋 Ключевых слов пока нет."
    await update.message.reply_text(text)

# Команда /remove_keyword
@admin_only
async def remove_keyword_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🗑 Отправь ключевое слово, которое хочешь удалить:\n"
        "Пример: `trending`"
    )
    context.user_data['awaiting_remove_keyword'] = True

# Команда /set_schedule
@admin_only
async def set_schedule_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⏰ Отправь интервал в часах:\n"
        "Пример: `3` (каждые 3 часа)\n"
        "Минимум: 1 час"
    )
    context.user_data['awaiting_schedule'] = True

# Команда /add_link
@admin_only
async def add_link_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔗 Отправь ссылку на Reel:\n"
        "Пример: `https://www.instagram.com/reel/...`"
    )
    context.user_data['awaiting_link'] = True

# Команда /parse
@admin_only
async def parse_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Запускаю парсинг...")
    run_parser()
    await update.message.reply_text("✅ Парсинг завершён. Проверь канал!")

# Команда /status
@admin_only
async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel = get_channel()
    keywords = get_all_keywords()
    schedule = get_schedule()
    accounts = get_all_accounts()
    
    text = "📊 **Текущие настройки:**\n\n"
    text += f"📢 Канал: {channel or 'не настроен'}\n"
    text += f"⏰ Интервал: каждые {schedule} часа(ов)\n"
    text += f"🔑 Ключевых слов: {len(keywords)}\n"
    text += f"👤 Аккаунтов: {len(accounts)}\n"
    
    if accounts:
        text += "\nАккаунты:\n"
        for acc_id, username, _, _, is_verified in accounts:
            status = "✅" if is_verified else "⚠️"
            text += f"  {status} {username}\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

# Обработчик сообщений (каналы, ключевые слова, расписание, ссылки)
@admin_only
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # Если бот ждёт канал
    if context.user_data.get('awaiting_channel'):
        channel_id = text if text.startswith('@') else f"@{text}"
        set_channel(channel_id)
        context.user_data['awaiting_channel'] = False
        await update.message.reply_text(f"✅ Канал `{channel_id}` сохранён!", parse_mode='Markdown')
        return
    
    # Если бот ждёт ключевое слово
    if context.user_data.get('awaiting_keyword'):
        keyword = text.replace('#', '').strip()
        if add_keyword(keyword):
            await update.message.reply_text(f"✅ Ключевое слово `{keyword}` добавлено!", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"⚠️ Ключевое слово `{keyword}` уже есть в списке.", parse_mode='Markdown')
        context.user_data['awaiting_keyword'] = False
        return
    
    # Если бот ждёт удаление ключевого слова
    if context.user_data.get('awaiting_remove_keyword'):
        remove_keyword(text.strip())
        context.user_data['awaiting_remove_keyword'] = False
        await update.message.reply_text(f"🗑 Ключевое слово `{text}` удалено!", parse_mode='Markdown')
        return
    
    # Если бот ждёт расписание
    if context.user_data.get('awaiting_schedule'):
        try:
            hours = int(text)
            if hours < 1:
                hours = 1
            set_schedule(hours)
            context.user_data['awaiting_schedule'] = False
            await update.message.reply_text(f"⏰ Расписание: каждые {hours} часа(ов)")
        except:
            await update.message.reply_text("❌ Отправь число!")
        return
    
    # Если бот ждёт ссылку
    if context.user_data.get('awaiting_link'):
        if 'instagram.com/reel/' in text:
            add_pending_link(text)
            context.user_data['awaiting_link'] = False
            await update.message.reply_text("✅ Ссылка добавлена в очередь!")
        else:
            await update.message.reply_text("❌ Это не похоже на ссылку на Reel.")
        return
    
    # Если это ссылка на Reel (автоматически)
    if 'instagram.com/reel/' in text:
        add_pending_link(text)
        await update.message.reply_text("🔗 Ссылка на Reel обнаружена и добавлена в очередь!")
        return
    
    # Если это код верификации (цифры)
    if text.isdigit() and len(text) >= 4:
        account = get_unverified_account()
        if account:
            acc_id, username, password = account
            await update.message.reply_text(f"🔄 Проверяю код для `{username}`...", parse_mode='Markdown')
            cl, error = login_account(username, password, verification_code=text)
            if cl:
                await update.message.reply_text(f"✅ Аккаунт `{username}` верифицирован!")
            else:
                await update.message.reply_text(f"❌ Ошибка: {error}")
        else:
            await update.message.reply_text("Нет аккаунтов для верификации.")
        return
    
    await update.message.reply_text("Используй команды из /start")

def main():
    # Инициализируем БД
    init_db()
    
    # Создаём приложение
    app = Application.builder().token(TOKEN).build()
    
    # Регистрируем команды
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('add_account', add_account_cmd))
    app.add_handler(CommandHandler('verify', verify))
    app.add_handler(CommandHandler('set_channel', set_channel_cmd))
    app.add_handler(CommandHandler('add_keyword', add_keyword_cmd))
    app.add_handler(CommandHandler('keywords', keywords_cmd))
    app.add_handler(CommandHandler('remove_keyword', remove_keyword_cmd))
    app.add_handler(CommandHandler('set_schedule', set_schedule_cmd))
    app.add_handler(CommandHandler('add_link', add_link_cmd))
    app.add_handler(CommandHandler('parse', parse_cmd))
    app.add_handler(CommandHandler('status', status_cmd))
    
    # Обработчик всех сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем планировщик
    start_scheduler()
    
    print("Бот запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()