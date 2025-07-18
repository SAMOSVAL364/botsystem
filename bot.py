import os
import logging
import sqlite3
from pathlib import Path
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from dotenv import load_dotenv

# --- НАСТРОЙКА ПУТЕЙ --- #
BOT_DIR = Path("C:/Users/Максим/Desktop/botsystem")
DB_PATH = BOT_DIR / "petshop.db"
ENV_PATH = BOT_DIR / ".env"

# --- ЗАГРУЗКА КОНФИГУРАЦИИ --- #
load_dotenv(ENV_PATH)
TOKEN = os.getenv("TOKEN")
# Список администраторов
ADMINS = [5634800132, 5515360616]  # Ваши администраторы

# --- НАСТРОЙКА ЛОГГИНГА --- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- БАЗА ДАННЫХ --- #
def init_db():
    """Инициализация базы данных"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                mutation TEXT NOT NULL,
                price INTEGER NOT NULL,
                category TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                join_date TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                pet_id INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(pet_id) REFERENCES pets(id)
            )
        """)
        conn.commit()

def add_user(user_id, username, first_name, last_name):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
            (user_id, username, first_name, last_name)
        )

def add_pet(name, mutation, price, category):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO pets (name, mutation, price, category) VALUES (?, ?, ?, ?)",
            (name, mutation, price, category)
        )
        conn.commit()
        return cursor.lastrowid

def delete_pet(pet_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pets WHERE id = ?", (pet_id,))
        conn.commit()
        return cursor.rowcount > 0

def get_pets_by_category(category):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pets WHERE category = ? ORDER BY name", (category,))
        return cursor.fetchall()

def get_pet(pet_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        return cursor.fetchone()

def get_all_pets():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pets ORDER BY category, name")
        return cursor.fetchall()

def create_purchase(user_id, pet_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO purchases (user_id, pet_id) VALUES (?, ?)",
            (user_id, pet_id)
        )
        conn.commit()
        return cursor.lastrowid

# --- ОСНОВНЫЕ ФУНКЦИИ БОТА --- #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    
    buttons = [
        [InlineKeyboardButton("🛒 Магазин питомцев", callback_data="shop_menu")],
        [InlineKeyboardButton("ℹ О боте", callback_data="about")]
    ]
    
    if user.id in ADMINS:
        buttons.append([InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(buttons)
    
    if update.message:
        await update.message.reply_text(
            f"Привет, {user.first_name}! Добро пожаловать в Pet Shop!",
            reply_markup=reply_markup
        )
    else:
        await update.callback_query.edit_message_text(
            f"Привет, {user.first_name}! Добро пожаловать в Pet Shop!",
            reply_markup=reply_markup
        )

async def shop_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    buttons = [
        [InlineKeyboardButton("🐟 Steal a Fish!", callback_data="category_fish")],
        [InlineKeyboardButton("🧠 Steal a Brainrot", callback_data="category_brainrot")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        "🛒 Магазин питомцев:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def show_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.split("_")[1]
    
    pets = get_pets_by_category(category)
    if not pets:
        buttons = [[InlineKeyboardButton("🔙 Назад", callback_data="shop_menu")]]
        await query.edit_message_text(
            f"ℹ В категории '{category}' пока нет питомцев",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return
    
    buttons = []
    for pet in pets:
        btn_text = f"{pet[1]} ({pet[2]}) - {pet[3]}₽"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"pet_{pet[0]}")])
    
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="shop_menu")])
    
    await query.edit_message_text(
        f"🐾 {category.capitalize()} в продаже:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def show_pet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    pet_id = int(query.data.split("_")[1])
    pet = get_pet(pet_id)
    
    if not pet:
        await query.edit_message_text("❌ Питомец не найден")
        return
        
    buttons = []
    if query.from_user.id in ADMINS:
        buttons.append([InlineKeyboardButton("🗑 Удалить", callback_data=f"confirm_delete_{pet[0]}")])
    buttons.append([InlineKeyboardButton("💰 Купить", callback_data=f"buy_{pet[0]}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data=f"category_{pet[4]}")])
    
    await query.edit_message_text(
        f"🐾 <b>{pet[1]}</b>\n"
        f"🧬 Мутация: {pet[2]}\n"
        f"💵 Цена: {pet[3]}₽\n"
        f"📁 Категория: {pet[4]}\n\n"
        f"🆔 ID: {pet[0]}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def handle_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    pet_id = int(query.data.split("_")[1])
    pet = get_pet(pet_id)
    
    if not pet:
        await query.edit_message_text("❌ Питомец не найден")
        return
        
    user = query.from_user
    purchase_id = create_purchase(user.id, pet_id)
    
    bot = Bot(token=TOKEN)
    
    # Уведомление всем админам
    for admin_id in ADMINS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"🛒 <b>Новый запрос на покупку #{purchase_id}</b>\n\n"
                     f"🐾 Питомец: {pet[1]} ({pet[2]})\n"
                     f"💵 Цена: {pet[3]}₽\n"
                     f"🆔 ID питомца: {pet[0]}\n\n"
                     f"👤 Покупатель: {user.first_name} (@{user.username or 'нет'})\n"
                     f"🆔 ID пользователя: {user.id}\n\n"
                     f"✅ Подтвердить: /confirm_{purchase_id}\n"
                     f"❌ Отклонить: /reject_{purchase_id}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✉️ Написать пользователю", url=f"tg://user?id={user.id}")],
                    [InlineKeyboardButton("🗑 Удалить питомца", callback_data=f"confirm_delete_{pet[0]}")]
                ])
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
    
    # Ответ пользователю
    await query.edit_message_text(
        "✅ <b>Запрос отправлен админам!</b>\n\n"
        f"Вы хотите купить: {pet[1]} ({pet[2]}) за {pet[3]}₽\n\n"
        "Ожидайте подтверждения. Если хотите уточнить детали, нажмите кнопку ниже:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✉️ Написать админу", url=f"tg://user?id={ADMINS[0]}")],
            [InlineKeyboardButton("🔙 Назад", callback_data=f"pet_{pet_id}")]
        ])
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in ADMINS:
        await query.edit_message_text("⛔ У вас нет прав доступа!")
        return
    
    buttons = [
        [InlineKeyboardButton("➕ Добавить питомца", callback_data="add_pet")],
        [InlineKeyboardButton("🗑 Удалить питомца", callback_data="delete_pet_menu")],
        [InlineKeyboardButton("📝 Список питомцев", callback_data="pet_list")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        "👑 <b>Админ-панель</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def add_pet_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['adding_pet'] = {'step': 'name', 'data': {}}
    
    await query.edit_message_text(
        "✍️ Введите <b>имя питомца</b>:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="admin_panel")]
        ])
    )

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'adding_pet' not in context.user_data:
        return
    
    text = update.message.text
    adding_data = context.user_data['adding_pet']
    
    if adding_data['step'] == 'name':
        adding_data['data']['name'] = text
        adding_data['step'] = 'mutation'
        await update.message.reply_text("✍️ Введите <b>мутацию питомца</b>:", parse_mode="HTML")
    elif adding_data['step'] == 'mutation':
        adding_data['data']['mutation'] = text
        adding_data['step'] = 'price'
        await update.message.reply_text("✍️ Введите <b>цену в рублях</b> (только число):", parse_mode="HTML")
    elif adding_data['step'] == 'price':
        try:
            adding_data['data']['price'] = int(text)
            adding_data['step'] = 'category'
            await update.message.reply_text("✍️ Введите <b>категорию</b> (fish/brainrot):", parse_mode="HTML")
        except ValueError:
            await update.message.reply_text("❌ Цена должна быть числом. Попробуйте еще раз:")
    elif adding_data['step'] == 'category':
        category = text.lower()
        if category in ['fish', 'brainrot']:
            pet_data = adding_data['data']
            pet_data['category'] = category
            pet_id = add_pet(**pet_data)
            
            await update.message.reply_text(
                f"✅ Питомец успешно добавлен!\n\n"
                f"🐾 Имя: {pet_data['name']}\n"
                f"🧬 Мутация: {pet_data['mutation']}\n"
                f"💵 Цена: {pet_data['price']}₽\n"
                f"📁 Категория: {pet_data['category']}\n"
                f"🆔 ID: {pet_id}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel")]
                ])
            )
            del context.user_data['adding_pet']
        else:
            await update.message.reply_text("❌ Категория должна быть 'fish' или 'brainrot'. Попробуйте еще раз:")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "main_menu":
        await start(update, context)
    elif query.data == "shop_menu":
        await shop_menu(update, context)
    elif query.data == "about":
        await query.edit_message_text(
            "🤖 <b>О боте Pet Shop</b>\n\n"
            "Этот бот позволяет покупать уникальных питомцев:\n"
            "🐟 Steal a Fish!\n"
            "🧠 Steal a Brainrot!\n\n"
            "Для связи используйте кнопку 'Написать админу'",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
            ])
        )
    elif query.data.startswith("category_"):
        await show_category(update, context)
    elif query.data.startswith("pet_"):
        await show_pet(update, context)
    elif query.data.startswith("buy_"):
        await handle_purchase(update, context)
    elif query.data == "admin_panel":
        await admin_panel(update, context)
    elif query.data == "add_pet":
        await add_pet_menu(update, context)
    elif query.data == "delete_pet_menu":
        pets = get_all_pets()
        if not pets:
            await query.edit_message_text(
                "ℹ Нет доступных питомцев для удаления",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
                ])
            )
            return
        
        buttons = [
            [InlineKeyboardButton(f"{pet[1]} (ID: {pet[0]}) - {pet[3]}₽", callback_data=f"pet_{pet[0]}")]
            for pet in pets
        ]
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
        
        await query.edit_message_text(
            "🗑 <b>Выберите питомца для удаления:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    elif query.data.startswith("confirm_delete_"):
        pet_id = int(query.data.split("_")[2])
        pet = get_pet(pet_id)
        
        await query.edit_message_text(
            f"❓ Вы точно хотите удалить питомца?\n\n"
            f"🐾 {pet[1]} ({pet[2]})\n"
            f"💵 {pet[3]}₽ | 📁 {pet[4]}\n"
            f"🆔 ID: {pet[0]}",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Да", callback_data=f"delete_{pet[0]}"),
                    InlineKeyboardButton("❌ Нет", callback_data=f"pet_{pet[0]}")
                ]
            ])
        )
    elif query.data.startswith("delete_"):
        pet_id = int(query.data.split("_")[1])
        if delete_pet(pet_id):
            await query.edit_message_text("✅ Питомец успешно удален!")
        else:
            await query.edit_message_text("❌ Не удалось удалить питомца")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'adding_pet' in context.user_data:
        await handle_admin_message(update, context)
    else:
        await update.message.reply_text("ℹ Используйте кнопки для навигации")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Ошибка в обработчике:", exc_info=context.error)
    if update and hasattr(update, 'callback_query'):
        try:
            await update.callback_query.edit_message_text("⚠ Произошла ошибка")
        except Exception as e:
            logger.error(f"Ошибка при обработке ошибки: {e}")

# --- ЗАПУСК БОТА --- #
def main():
    init_db()
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    logger.info(f"Бот запущен! Администраторы: {ADMINS}")
    app.run_polling()

if __name__ == "__main__":
    main()