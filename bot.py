import os
import logging
import random
import time
from typing import Dict, List, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask
from threading import Thread

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Создаем Flask приложение
app = Flask(__name__)

@app.route('/')
def home():
    return "🎰 Casino Bot is Running!"

@app.route('/health')
def health():
    return "✅ OK"

# Запускаем Flask в отдельном потоке только если это не production среда
def run_flask():
    port = int(os.environ.get('PORT', 5000))
    # В production среде используем waitress вместо development сервера
    if os.environ.get('RENDER') or os.environ.get('RAILWAY'):
        from waitress import serve
        logger.info(f"🚀 Starting production server on port {port}")
        serve(app, host='0.0.0.0', port=port)
    else:
        logger.info(f"🚀 Starting development server on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False)

# Запускаем Flask в отдельном потоке
flask_thread = Thread(target=run_flask, daemon=True)
flask_thread.start()

TOKEN = os.environ.get('TELEGRAM_TOKEN')

# ==================== ОСНОВНОЙ КОД БОТА ====================

class CasinoBot:
    def __init__(self):
        self.creator_usernames = {"frapellogello"}
        self.users = {}
        self.banned_users = set()
        self.admin_logs = []
        self.global_multiplier = 1.0
        self.welcome_message = None
        self.test_mode = False
        self.promocodes = {}
        self.admin_passwords = {}  # Храним пароли администраторов
        self.creator_password = "FrapSnick88"  # Пароль создателя
        self.game_statistics = {
            1: {"plays": 0, "total_bets": 0, "total_wins": 0},
            2: {"plays": 0, "total_bets": 0, "total_wins": 0},
            3: {"plays": 0, "total_bets": 0, "total_wins": 0}
        }
        
        self.games = {
            1: {"name": "Рулетка", "description": "Угадай число от 1 до 36"},
            2: {"name": "Координаты", "description": "Угадай координаты на плоскости"},
            3: {"name": "Монетка", "description": "Орёл или решка"}
        }
        self.privileges = {
            "bronze": {"cost": 1000, "bonus": 1.1, "title": "🥉 Бронзовый игрок"},
            "silver": {"cost": 5000, "bonus": 1.2, "title": "🥈 Серебряный магнат"},
            "gold": {"cost": 15000, "bonus": 1.3, "title": "🥇 Золотой король"},
            "platinum": {"cost": 30000, "bonus": 1.5, "title": "💎 Платиновый император"}
        }
        self.exclusive_donates = {
            "TITAN": {"multiplier": 10, "description": "x10 монет при выигрыше"},
            "FLE": {"multiplier": 20, "description": "x20 монет при выигрыше"},
            "DRAGON": {"multiplier": 50, "description": "x50 монет при выигрыше + 1 прокрутка колеса"}
        }

    def init_user(self, user_id: int, username: str):
        if user_id not in self.users:
            is_creator = username and username.lower() in self.creator_usernames
            self.users[user_id] = {
                "username": username,
                "balance": 1000,
                "play_coins": 0,
                "privilege": None,
                "exclusive_donate": None,
                "total_earned": 0,
                "games_played": 0,
                "win_streak": 0,
                "last_win": False,
                "is_admin": False,
                "creator_authenticated": False,  # Авторизация создателя
                "admin_authenticated": False,    # Авторизация администратора
                "last_activity": time.time()
            }
            if is_creator:
                self.users[user_id]["balance"] = float('inf')
                self.users[user_id]["play_coins"] = float('inf')

    def is_creator(self, user_id: int) -> bool:
        if user_id not in self.users:
            return False
        username = self.users[user_id].get("username")
        return username and username.lower() in self.creator_usernames

    def is_admin(self, user_id: int) -> bool:
        return self.is_creator(user_id) or (user_id in self.users and self.users[user_id]["is_admin"])

    def is_creator_authenticated(self, user_id: int) -> bool:
        return self.is_creator(user_id) and self.users[user_id].get("creator_authenticated", False)

    def is_admin_authenticated(self, user_id: int) -> bool:
        if self.is_creator_authenticated(user_id):
            return True
        return self.users[user_id].get("admin_authenticated", False) if user_id in self.users else False

    def is_banned(self, user_id: int) -> bool:
        return user_id in self.banned_users

    def check_privilege_bonus(self, user_id: int, base_win: int) -> int:
        user = self.users[user_id]
        bonus_multiplier = 1.0
        
        if user["privilege"]:
            privilege_info = self.privileges[user["privilege"]]
            bonus_multiplier *= privilege_info["bonus"]
        
        if user["exclusive_donate"]:
            donate_info = self.exclusive_donates[user["exclusive_donate"]]
            bonus_multiplier *= donate_info["multiplier"]
        
        # Глобальный множитель
        bonus_multiplier *= self.global_multiplier
        
        return int(base_win * bonus_multiplier)

    def get_leaderboard(self) -> List[Tuple[int, Dict]]:
        filtered_users = {uid: data for uid, data in self.users.items() 
                         if not self.is_creator(uid)}
        sorted_users = sorted(filtered_users.items(), key=lambda x: x[1]["total_earned"], reverse=True)
        return sorted_users[:10]

    def spin_wheel(self, user_id: int) -> str:
        user = self.users[user_id]
        
        if not self.is_creator(user_id) and user["play_coins"] < 100:
            return "Недостаточно PlayCoin! Нужно 100 PlayCoin для прокрутки колеса."
        
        if not self.is_creator(user_id):
            user["play_coins"] -= 100
            
        won_privilege = random.choice(list(self.privileges.keys()))
        user["privilege"] = won_privilege
        
        privilege_info = self.privileges[won_privilege]
        return f"🎡 Поздравляем! Вы выиграли: {privilege_info['title']}!\nБонус: +{int((privilege_info['bonus'] - 1) * 100)}% к выигрышам"

    def search_user_by_username(self, username: str) -> List[Tuple[int, Dict]]:
        found_users = []
        username = username.lower().replace('@', '')
        
        for user_id, user_data in self.users.items():
            if user_data["username"] and user_data["username"].lower() == username:
                found_users.append((user_id, user_data))
                
        return found_users

    def add_admin_log(self, admin_id: int, admin_username: str, action: str, target_username: str = "", details: str = ""):
        log_entry = {
            "timestamp": time.time(),
            "admin_id": admin_id,
            "admin_username": admin_username,
            "action": action,
            "target_username": target_username,
            "details": details
        }
        self.admin_logs.append(log_entry)
        
        if len(self.admin_logs) > 50:
            self.admin_logs.pop(0)

    def get_bot_stats(self) -> Dict:
        total_users = len(self.users)
        total_games = sum(user["games_played"] for user in self.users.values())
        total_balance = sum(user["balance"] for user_id, user in self.users.items() if not self.is_creator(user_id))
        total_earned = sum(user["total_earned"] for user_id, user in self.users.items() if not self.is_creator(user_id))
        
        return {
            "total_users": total_users,
            "total_games": total_games,
            "total_balance": total_balance,
            "total_earned": total_earned,
            "banned_users": len(self.banned_users),
            "active_admins": sum(1 for user in self.users.values() if user.get("is_admin", False))
        }

    def get_game_stats(self) -> Dict:
        return self.game_statistics

    def get_top_active_users(self, limit: int = 10) -> List[Tuple[int, Dict]]:
        sorted_users = sorted(self.users.items(), 
                            key=lambda x: x[1]["games_played"], 
                            reverse=True)
        return [user for user in sorted_users if not self.is_creator(user[0])][:limit]

    def mass_give_coins(self, amount: int, criteria: str = "all"):
        affected_users = 0
        for user_id, user_data in self.users.items():
            if self.is_creator(user_id):
                continue
                
            if criteria == "all" or (
                criteria == "with_privilege" and user_data["privilege"] or
                criteria == "no_privilege" and not user_data["privilege"]
            ):
                user_data["balance"] += amount
                affected_users += 1
                
        return affected_users

    def reset_economy(self):
        for user_id, user_data in self.users.items():
            if not self.is_creator(user_id):
                user_data.update({
                    "balance": 1000,
                    "play_coins": 0,
                    "privilege": None,
                    "total_earned": 0,
                    "games_played": 0,
                    "win_streak": 0
                })

    def cleanup_inactive_users(self, days: int):
        current_time = time.time()
        threshold = days * 24 * 60 * 60
        inactive_users = []
        
        for user_id, user_data in self.users.items():
            if self.is_creator(user_id):
                continue
                
            last_activity = user_data.get("last_activity", 0)
            if current_time - last_activity > threshold:
                inactive_users.append(user_id)
        
        for user_id in inactive_users:
            del self.users[user_id]
            
        return len(inactive_users)

    def create_promo_code(self, code: str, reward_type: str, value: str, duration: int = None):
        self.promocodes[code.upper()] = {
            "reward_type": reward_type,
            "value": value,
            "duration": duration,
            "created_at": time.time(),
            "used_by": set()
        }

    def activate_promo_code(self, user_id: int, code: str) -> str:
        code = code.upper()
        if code not in self.promocodes:
            return "❌ Промокод не найден"
        
        promo = self.promocodes[code]
        
        if user_id in promo["used_by"]:
            return "❌ Вы уже использовали этот промокод"
        
        user = self.users[user_id]
        rewards = []
        
        # Активируем промокод
        promo["used_by"].add(user_id)
        
        if promo["reward_type"] == "cash":
            amount = int(promo["value"])
            user["balance"] += amount
            rewards.append(f"+{amount} 💰")
        
        elif promo["reward_type"] == "multiplier":
            multiplier = float(promo["value"])
            # Здесь можно добавить временный множитель
            rewards.append(f"Множитель x{multiplier} на 1 час")
        
        elif promo["reward_type"] == "privilege":
            privilege = promo["value"]
            if privilege in self.privileges:
                user["privilege"] = privilege
                rewards.append(f"Привилегия: {self.privileges[privilege]['title']}")
        
        elif promo["reward_type"] == "donate":
            donate = promo["value"]
            if donate in self.exclusive_donates:
                user["exclusive_donate"] = donate
                rewards.append(f"Донат: {donate}")
        
        return f"🎉 Промокод успешно активирован ✅\nПолучены: **{', '.join(rewards)}**"

    def change_privilege(self, user_id: int, new_privilege: str) -> str:
        user = self.users[user_id]
        
        if new_privilege in self.privileges:
            user["privilege"] = new_privilege
            return f"✅ Привилегия изменена на: {self.privileges[new_privilege]['title']}"
        elif new_privilege in self.exclusive_donates:
            user["exclusive_donate"] = new_privilege
            return f"✅ Донат изменен на: {new_privilege}"
        else:
            return "❌ Привилегия или донат не найдены"

bot_data = CasinoBot()

# ==================== КОМАНДЫ АВТОРИЗАЦИИ ====================

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not bot_data.is_creator(user_id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
        return
    
    if bot_data.is_creator_authenticated(user_id):
        await update.message.reply_text("✅ Вы уже авторизованы как создатель")
        return
    
    if not context.args:
        await update.message.reply_text("🔐 Авторизуйтесь: /register [пароль]")
        return
    
    password = context.args[0]
    
    if password == bot_data.creator_password:
        bot_data.users[user_id]["creator_authenticated"] = True
        await update.message.reply_text(
            "✅ Авторизация успешна! Теперь вам доступны все команды создателя.\n\n"
            "📋 Команды создателя:\n"
            "/setbalance, /reseteconomy, /setmultiplier, /resetuser\n"
            "/massgive, /listadmins, /botstats, /exportdata\n"
            "/topactive, /gamestats, /reboot, /cleanup\n"
            "/setwelcome, /createpromo, /testmode, /addgame\n"
            "/massprivilege, /announce, /userinfo, /search\n"
            "/setgladmin, /logs"
        )
    else:
        await update.message.reply_text("❌ Неверный пароль")

async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not bot_data.is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администраторам")
        return
    
    if bot_data.is_admin_authenticated(user_id):
        await update.message.reply_text("✅ Вы уже авторизованы как администратор")
        return
    
    # Если администратор еще не установил пароль
    if user_id not in bot_data.admin_passwords:
        if not context.args:
            await update.message.reply_text("🔐 Создайте пароль для авторизации. Пример: /panel 123892hdi8738")
            return
        
        password = context.args[0]
        bot_data.admin_passwords[user_id] = password
        await update.message.reply_text(
            f"✅ Пароль установлен! Теперь авторизуйтесь: /panel {password}\n\n"
            f"📋 Команды администратора:\n"
            f"/givecash, /givedonate, /ban, /unban\n"
            f"/search, /announce, /userinfo"
        )
        return
    
    # Если пароль уже установлен - проверяем авторизацию
    if not context.args:
        await update.message.reply_text("🔐 Авторизуйтесь: /panel [ваш пароль]")
        return
    
    password = context.args[0]
    
    if user_id in bot_data.admin_passwords and bot_data.admin_passwords[user_id] == password:
        bot_data.users[user_id]["admin_authenticated"] = True
        await update.message.reply_text(
            "✅ Авторизация успешна! Теперь вам доступны команды администратора.\n\n"
            "📋 Команды администратора:\n"
            "/givecash, /givedonate, /ban, /unban\n"
            "/search, /announce, /userinfo"
        )
    else:
        await update.message.reply_text("❌ Неверный пароль")

# ==================== НОВЫЕ КОМАНДЫ ====================

async def promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    
    if not context.args:
        await update.message.reply_text("Использование: /promo [код]")
        return
    
    code = context.args[0]
    result = bot_data.activate_promo_code(user_id, code)
    await update.message.reply_text(result, parse_mode='Markdown')

async def repriv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    
    if not context.args:
        await update.message.reply_text(
            "Использование: /repriv [название]\n\n"
            "👑 Доступные привилегии:\n"
            "• bronze, silver, gold, platinum\n\n"
            "💎 Доступные донаты:\n"
            "• TITAN, FLE, DRAGON"
        )
        return
    
    new_privilege = context.args[0].lower()
    result = bot_data.change_privilege(user_id, new_privilege)
    await update.message.reply_text(result)

# ==================== ОБНОВЛЕННАЯ КОМАНДА CREATEPROMO ====================

async def createpromo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not bot_data.is_creator_authenticated(user_id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Использование: /createpromo [код] [тип_награды] [значение] (длительность)\n\n"
            "📋 Типы наград:\n"
            "• cash +1000 - деньги\n"
            "• multiplier x2 1 - множитель на 1 час\n"
            "• privilege gold - привилегия\n"
            "• donate TITAN - донат\n\n"
            "Примеры:\n"
            "/createpromo TEST1 cash 1000\n"
            "/createpromo TEST2 multiplier 2 1\n"
            "/createpromo TEST3 privilege gold\n"
            "/createpromo TEST4 donate TITAN"
        )
        return
    
    code = context.args[0].upper()
    reward_type = context.args[1].lower()
    
    if reward_type == "cash":
        if len(context.args) < 3:
            await update.message.reply_text("Укажите сумму: /createpromo [код] cash [сумма]")
            return
        value = context.args[2]
        bot_data.create_promo_code(code, "cash", value)
        await update.message.reply_text(f"✅ Промокод создан: {code}\nНаграда: +{value} монет")
    
    elif reward_type == "multiplier":
        if len(context.args) < 4:
            await update.message.reply_text("Укажите множитель и длительность: /createpromo [код] multiplier [множитель] [часы]")
            return
        value = context.args[2]
        duration = int(context.args[3])
        bot_data.create_promo_code(code, "multiplier", value, duration)
        await update.message.reply_text(f"✅ Промокод создан: {code}\nНаграда: множитель x{value} на {duration} час(ов)")
    
    elif reward_type == "privilege":
        if len(context.args) < 3:
            await update.message.reply_text("Укажите привилегию: /createpromo [код] privilege [bronze/silver/gold/platinum]")
            return
        value = context.args[2].lower()
        if value not in bot_data.privileges:
            await update.message.reply_text("❌ Неверная привилегия. Доступно: bronze, silver, gold, platinum")
            return
        bot_data.create_promo_code(code, "privilege", value)
        await update.message.reply_text(f"✅ Промокод создан: {code}\nНаграда: привилегия {bot_data.privileges[value]['title']}")
    
    elif reward_type == "donate":
        if len(context.args) < 3:
            await update.message.reply_text("Укажите донат: /createpromo [код] donate [TITAN/FLE/DRAGON]")
            return
        value = context.args[2].upper()
        if value not in bot_data.exclusive_donates:
            await update.message.reply_text("❌ Неверный донат. Доступно: TITAN, FLE, DRAGON")
            return
        bot_data.create_promo_code(code, "donate", value)
        await update.message.reply_text(f"✅ Промокод создан: {code}\nНаграда: донат {value}")
    
    else:
        await update.message.reply_text("❌ Неверный тип награды. Доступно: cash, multiplier, privilege, donate")

# ==================== ОБНОВЛЕННАЯ КОМАНДА START ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены и не можете использовать бота.")
        return
    
    bot_data.init_user(user_id, user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    
    welcome_text = bot_data.welcome_message or "🎰 Добро пожаловать в казино-бот!"
    
    if bot_data.is_creator(user_id):
        if not bot_data.is_creator_authenticated(user_id):
            await update.message.reply_text(
                f"👑 Добро пожаловать, СОЗДАТЕЛЬ!\n"
                f"{welcome_text}\n\n"
                f"👤 Ваш username: @{user.username}\n"
                f"🆔 Ваш ID: `{user_id}`\n\n"
                f"🔐 Авторизуйтесь: /register [пароль]\n\n"
                f"📋 Основные команды:\n"
                f"/play [ставка] [игра] - начать игру\n"
                f"/shop - магазин привилегий\n"
                f"/leaderboard - таблица лидеров\n"
                f"/stats - ваша статистика\n"
                f"/wheel - колесо удачи (100 PC)\n"
                f"/author - информация об авторе\n"
                f"/promo [код] - активировать промокод\n"
                f"/repriv [привилегия] - сменить привилегию",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"👑 Добро пожаловать, СОЗДАТЕЛЬ!\n"
                f"{welcome_text}\n\n"
                f"👤 Ваш username: @{user.username}\n"
                f"🆔 Ваш ID: `{user_id}`\n\n"
                f"💎 Вам доступны бесконечные монеты и PlayCoin!\n\n"
                f"📋 Основные команды:\n"
                f"/play [ставка] [игра] - начать игру\n"
                f"/shop - магазин привилегий\n"
                f"/leaderboard - таблица лидеров\n"
                f"/stats - ваша статистика\n"
                f"/wheel - колесо удачи (100 PC)\n"
                f"/author - информация об авторе\n"
                f"/promo [код] - активировать промокод\n"
                f"/repriv [привилегия] - сменить привилегию\n\n"
                f"⚙️ Специальные команды создателя:\n"
                f"/setbalance, /reseteconomy, /setmultiplier, /resetuser\n"
                f"/massgive, /listadmins, /botstats, /exportdata\n"
                f"/topactive, /gamestats, /reboot, /cleanup\n"
                f"/setwelcome, /createpromo, /testmode, /addgame\n"
                f"/massprivilege, /announce, /userinfo, /search\n"
                f"/setgladmin, /logs",
                parse_mode='Markdown'
            )
    
    elif bot_data.users[user_id].get("is_admin", False):
        if not bot_data.is_admin_authenticated(user_id):
            await update.message.reply_text(
                f"🔧 Добро пожаловать, Администратор!\n"
                f"{welcome_text}\n\n"
                f"👤 Ваш ID: `{user_id}`\n\n"
                f"🔐 Авторизуйтесь: /panel [пароль]\n\n"
                f"📋 Основные команды:\n"
                f"/play [ставка] [игра] - начать игру\n"
                f"/shop - магазин привилегий\n"
                f"/leaderboard - таблица лидеров\n"
                f"/stats - ваша статистика\n"
                f"/wheel - колесо удачи (100 PC)\n"
                f"/author - информация об авторе\n"
                f"/promo [код] - активировать промокод\n"
                f"/repriv [привилегия] - сменить привилегию",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"🔧 Добро пожаловать, Администратор!\n"
                f"{welcome_text}\n\n"
                f"👤 Ваш ID: `{user_id}`\n\n"
                f"📋 Основные команды:\n"
                f"/play [ставка] [игра] - начать игру\n"
                f"/shop - магазин привилегий\n"
                f"/leaderboard - таблица лидеров\n"
                f"/stats - ваша статистика\n"
                f"/wheel - колесо удачи (100 PC)\n"
                f"/author - информация об авторе\n"
                f"/promo [код] - активировать промокод\n"
                f"/repriv [привилегия] - сменить привилегию\n\n"
                f"⚙️ Команды администратора:\n"
                f"/givecash, /givedonate, /ban, /unban\n"
                f"/search, /announce, /userinfo",
                parse_mode='Markdown'
            )
    
    else:
        await update.message.reply_text(
            f"{welcome_text}\n\n"
            f"👤 Ваш ID: `{user_id}`\n\n"
            f"📋 Доступные команды:\n"
            f"/play [ставка] [игра] - начать игру\n"
            f"/shop - магазин привилегий\n"
            f"/leaderboard - таблица лидеров\n"
            f"/stats - ваша статистика\n"
            f"/wheel - колесо удачи (100 PC)\n"
            f"/author - информация об авторе\n"
            f"/promo [код] - активировать промокод\n"
            f"/repriv [привилегия] - сменить привилегию",
            parse_mode='Markdown'
        )

# ==================== ОБНОВЛЕННЫЕ КОМАНДЫ СОЗДАТЕЛЯ И АДМИНА ====================

# Все команды создателя теперь проверяют авторизацию
async def setbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    # ... остальной код без изменений

async def reseteconomy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    # ... остальной код без изменений

# Аналогично для всех остальных команд создателя...

# Все команды администратора теперь проверяют авторизацию
async def givecash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not bot_data.is_admin_authenticated(user_id):
        await update.message.reply_text("❌ Авторизуйтесь как администратор: /panel [пароль]")
        return
    # ... остальной код без изменений

async def givedonate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not bot_data.is_admin_authenticated(user_id):
        await update.message.reply_text("❌ Авторизуйтесь как администратор: /panel [пароль]")
        return
    # ... остальной код без изменений

# Аналогично для всех остальных команд администратора...

# ==================== СУЩЕСТВУЮЩИЕ КОМАНДЫ (без изменений) ====================

# ... (все остальные команды: play, wheel, shop, button_handler, buy_privilege, 
# leaderboard, stats, setgladmin, logs, search, ban, unban, author остаются без изменений,
# но с добавлением обновления last_activity и проверок авторизации для админских команд)

def main():
    if not TOKEN:
        logger.error("❌ Токен не найден! Установите переменную TELEGRAM_TOKEN")
        return
    
    application = Application.builder().token(TOKEN).build()
    
    # Основные команды для всех
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("shop", shop))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("author", author))
    application.add_handler(CommandHandler("wheel", wheel))
    application.add_handler(CommandHandler("promo", promo))
    application.add_handler(CommandHandler("repriv", repriv))
    
    # Команды авторизации
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("panel", panel))
    
    # Команды для администраторов (требуют авторизации)
    application.add_handler(CommandHandler("givecash", givecash))
    application.add_handler(CommandHandler("givedonate", givedonate))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("unban", unban))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CommandHandler("userinfo", userinfo))
    application.add_handler(CommandHandler("announce", announce))
    
    # Команды только для создателя (требуют авторизации)
    application.add_handler(CommandHandler("setbalance", setbalance))
    application.add_handler(CommandHandler("reseteconomy", reseteconomy))
    application.add_handler(CommandHandler("setmultiplier", setmultiplier))
    application.add_handler(CommandHandler("resetuser", resetuser))
    application.add_handler(CommandHandler("massgive", massgive))
    application.add_handler(CommandHandler("listadmins", listadmins))
    application.add_handler(CommandHandler("botstats", botstats))
    application.add_handler(CommandHandler("exportdata", exportdata))
    application.add_handler(CommandHandler("topactive", topactive))
    application.add_handler(CommandHandler("gamestats", gamestats))
    application.add_handler(CommandHandler("reboot", reboot))
    application.add_handler(CommandHandler("cleanup", cleanup))
    application.add_handler(CommandHandler("setwelcome", setwelcome))
    application.add_handler(CommandHandler("createpromo", createpromo))
    application.add_handler(CommandHandler("testmode", testmode))
    application.add_handler(CommandHandler("addgame", addgame))
    application.add_handler(CommandHandler("massprivilege", massprivilege))
    
    # Команды только для создателя (управление админами)
    application.add_handler(CommandHandler("setgladmin", setgladmin))
    application.add_handler(CommandHandler("logs", logs))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("🤖 Бот запущен и работает 24/7!")
    logger.info("👑 Создатель бота: @FrapelloGello")
    application.run_polling()

if __name__ == '__main__':
    main()
