import os
import logging
import random
import time
import json
import threading
from typing import Dict, List, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Простой HTTP сервер для Render
try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
    
    def log_message(self, format, *args):
        return

def run_health_server():
    port = int(os.environ.get('PORT', 5000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    logger.info(f"🌐 Health server running on port {port}")
    server.serve_forever()

health_thread = threading.Thread(target=run_health_server, daemon=True)
health_thread.start()

TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TOKEN:
    logger.error("❌ TELEGRAM_TOKEN не установлен!")
    raise ValueError("TELEGRAM_TOKEN не найден в переменных окружения")

class CasinoBot:
    def __init__(self):
        self.data_file = "bot_data.json"
        self.creator_usernames = {"frapellogello"}
        self.users = {}
        self.banned_users = set()
        self.admin_logs = []
        self.global_multiplier = 1.0
        self.welcome_message = None
        self.test_mode = False
        self.promocodes = {}
        self.admin_passwords = {}
        self.creator_password = "FrapSnick88"
        self.last_reply_time = {}
        
        self.game_statistics = {
            1: {"plays": 0, "total_bets": 0, "total_wins": 0},
            2: {"plays": 0, "total_bets": 0, "total_wins": 0},
            3: {"plays": 0, "total_bets": 0, "total_wins": 0},
            4: {"plays": 0, "total_bets": 0, "total_wins": 0}
        }
        
        self.games = {
            1: {"name": "🎡 Рулетка", "description": "Угадай число от 1 до 36"},
            2: {"name": "🎯 Координаты", "description": "Угадай координаты на плоскости"},
            3: {"name": "🪙 Монетка", "description": "Орёл или решка"},
            4: {"name": "🍀 Удача", "description": "50/50 шанс выиграть x2"}
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
        
        self.load_data()

    def save_data(self):
        try:
            data = {
                'users': self.users,
                'banned_users': list(self.banned_users),
                'admin_logs': self.admin_logs,
                'global_multiplier': self.global_multiplier,
                'welcome_message': self.welcome_message,
                'test_mode': self.test_mode,
                'promocodes': self.promocodes,
                'admin_passwords': self.admin_passwords,
                'game_statistics': self.game_statistics,
                'last_reply_time': self.last_reply_time
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("💾 Данные успешно сохранены")
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении данных: {e}")

    def load_data(self):
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.users = data.get('users', {})
                self.banned_users = set(data.get('banned_users', []))
                self.admin_logs = data.get('admin_logs', [])
                self.global_multiplier = data.get('global_multiplier', 1.0)
                self.welcome_message = data.get('welcome_message')
                self.test_mode = data.get('test_mode', False)
                self.promocodes = data.get('promocodes', {})
                self.admin_passwords = data.get('admin_passwords', {})
                self.game_statistics = data.get('game_statistics', self.game_statistics)
                self.last_reply_time = data.get('last_reply_time', {})
                
                self.users = {int(k): v for k, v in self.users.items()}
                
                logger.info("💾 Данные успешно загружены")
            else:
                logger.info("📝 Файл данных не найден, создаем новую базу")
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке данных: {e}")

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
                "creator_authenticated": False,
                "admin_authenticated": False,
                "creator_auth_time": 0,
                "admin_auth_time": 0,
                "last_activity": time.time(),
                "last_daily": 0,
                "daily_streak": 0,
                "bank_accounts": []
            }
            if is_creator:
                self.users[user_id]["balance"] = float('inf')
                self.users[user_id]["play_coins"] = float('inf')
            self.save_data()

    def is_creator(self, user_id: int) -> bool:
        if user_id not in self.users:
            return False
        username = self.users[user_id].get("username")
        return username and username.lower() in self.creator_usernames

    def is_admin(self, user_id: int) -> bool:
        return self.is_creator(user_id) or (user_id in self.users and self.users[user_id]["is_admin"])

    def is_creator_authenticated(self, user_id: int) -> bool:
        if not self.is_creator(user_id):
            return False
        auth_time = self.users[user_id].get("creator_auth_time", 0)
        if time.time() - auth_time > 24 * 3600:
            self.users[user_id]["creator_authenticated"] = False
            self.save_data()
            return False
        return self.users[user_id].get("creator_authenticated", False)

    def is_admin_authenticated(self, user_id: int) -> bool:
        if self.is_creator_authenticated(user_id):
            return True
        if user_id not in self.users:
            return False
        auth_time = self.users[user_id].get("admin_auth_time", 0)
        if time.time() - auth_time > 24 * 3600:
            self.users[user_id]["admin_authenticated"] = False
            self.save_data()
            return False
        return self.users[user_id].get("admin_authenticated", False)

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
        self.save_data()
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
        self.save_data()

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
                
        self.save_data()
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
        self.save_data()

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
            
        self.save_data()
        return len(inactive_users)

    def create_promo_code(self, code: str, reward_type: str, value: str, duration: int = None):
        self.promocodes[code.upper()] = {
            "reward_type": reward_type,
            "value": value,
            "duration": duration,
            "created_at": time.time(),
            "used_by": set()
        }
        self.save_data()

    def activate_promo_code(self, user_id: int, code: str) -> str:
        code = code.upper()
        if code not in self.promocodes:
            return "❌ Промокод не найден"
        
        promo = self.promocodes[code]
        
        if user_id in promo["used_by"]:
            return "❌ Вы уже использовали этот промокод"
        
        user = self.users[user_id]
        rewards = []
        
        promo["used_by"].add(user_id)
        
        if promo["reward_type"] == "cash":
            amount = int(promo["value"])
            user["balance"] += amount
            rewards.append(f"+{amount} 💰")
        
        elif promo["reward_type"] == "multiplier":
            multiplier = float(promo["value"])
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
        
        self.save_data()
        return f"🎉 Промокод успешно активирован ✅\nПолучены: **{', '.join(rewards)}**"

    def change_privilege(self, user_id: int, new_privilege: str) -> str:
        user = self.users[user_id]
        
        if new_privilege in self.privileges:
            user["privilege"] = new_privilege
            self.save_data()
            return f"✅ Привилегия изменена на: {self.privileges[new_privilege]['title']}"
        elif new_privilege in self.exclusive_donates:
            user["exclusive_donate"] = new_privilege
            self.save_data()
            return f"✅ Донат изменен на: {new_privilege}"
        else:
            return "❌ Привилегия или донат не найдены"

    def can_user_reply(self, user_id: int) -> Tuple[bool, str]:
        current_time = time.time()
        last_reply = self.last_reply_time.get(user_id, 0)
        
        if current_time - last_reply < 300:
            wait_time = 300 - int(current_time - last_reply)
            return False, f"❌ Вы можете ответить снова через {wait_time} секунд"
        
        return True, ""

    def create_bank_account(self, user_id: int, account_name: str) -> str:
        user = self.users[user_id]
        
        if len(user.get("bank_accounts", [])) >= 3:
            return "❌ У вас уже есть максимальное количество счетов (3)"
        
        if "bank_accounts" not in user:
            user["bank_accounts"] = []
        
        for account in user["bank_accounts"]:
            if account["name"].lower() == account_name.lower():
                return "❌ Счет с таким названием уже существует"
        
        user["bank_accounts"].append({
            "name": account_name,
            "balance": 0
        })
        
        self.save_data()
        return f"✅ Банковский счет '{account_name}' успешно создан!"

    def bank_deposit(self, user_id: int, account_index: int, amount: int) -> str:
        user = self.users[user_id]
        
        if "bank_accounts" not in user or not user["bank_accounts"]:
            return "❌ У вас нет банковских счетов. Создайте счет командой /regbank"
        
        if account_index < 0 or account_index >= len(user["bank_accounts"]):
            return "❌ Неверный номер счета"
        
        if amount <= 0:
            return "❌ Сумма должна быть положительной"
        
        if user["balance"] < amount:
            return "❌ Недостаточно средств на основном балансе"
        
        user["balance"] -= amount
        user["bank_accounts"][account_index]["balance"] += amount
        
        self.save_data()
        return f"✅ Успешно переведено {amount}💰 на счет '{user['bank_accounts'][account_index]['name']}'\n💳 Основной баланс: {user['balance']}"

    def bank_withdraw(self, user_id: int, account_index: int, amount: int) -> str:
        user = self.users[user_id]
        
        if "bank_accounts" not in user or not user["bank_accounts"]:
            return "❌ У вас нет банковских счетов. Создайте счет командой /regbank"
        
        if account_index < 0 or account_index >= len(user["bank_accounts"]):
            return "❌ Неверный номер счета"
        
        if amount <= 0:
            return "❌ Сумма должна быть положительной"
        
        if user["bank_accounts"][account_index]["balance"] < amount:
            return f"❌ Недостаточно средств на счете. Доступно: {user['bank_accounts'][account_index]['balance']}💰"
        
        user["bank_accounts"][account_index]["balance"] -= amount
        user["balance"] += amount
        
        self.save_data()
        return f"✅ Успешно снято {amount}💰 со счета '{user['bank_accounts'][account_index]['name']}'\n💳 Основной баланс: {user['balance']}"

bot_data = CasinoBot()

# ==================== КОМАНДЫ ====================

def help_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    help_text = """
🤖 **КОМАНДЫ БОТА** 🤖

🎮 **Игры:**
/play [ставка] [игра] - сыграть в игру
/wheel - колесо удачи (100 PC)

💰 **Экономика:**
/balance - ваш баланс
/daily - ежедневная награда
/transfer [@username/ID] [сумма] - перевести деньги

🏦 **Банк:**
/regbank [название] - создать банковский счет
/bank - управление счетами
/infobank - информация о счетах

📊 **Информация:**
/stats - ваша статистика
/leaderboard - таблица лидеров
/shop - магазин привилегий

🎁 **Дополнительно:**
/promo [код] - активировать промокод
/repriv [привилегия] - сменить привилегию
/author - информация об авторе
/q [сообщение] - ответить администрации

💡 **Игры:**
1. 🎡 Рулетка (1-36)
2. 🎯 Координаты  
3. 🪙 Монетка
4. 🍀 Удача (50/50)
    """
    
    update.message.reply_text(help_text, parse_mode='Markdown')

def balance(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    user = bot_data.users[user_id]
    
    total_bank = sum(account["balance"] for account in user.get("bank_accounts", []))
    
    balance_text = f"""
💰 **ВАШ БАЛАНС**

💳 Основные средства: {user['balance']}💰
🎯 PlayCoin: {user['play_coins']} PC
🏦 В банке: {total_bank}💰

📈 Всего заработано: {user['total_earned']}💰
🎮 Сыграно игр: {user['games_played']}
    """
    
    update.message.reply_text(balance_text, parse_mode='Markdown')

def daily(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    user = bot_data.users[user_id]
    
    current_time = time.time()
    last_daily = user.get("last_daily", 0)
    
    if current_time - last_daily < 24 * 3600:
        wait_time = 24 * 3600 - int(current_time - last_daily)
        hours = wait_time // 3600
        minutes = (wait_time % 3600) // 60
        update.message.reply_text(f"⏰ Следующая награда через {hours}ч {minutes}м")
        return
    
    daily_streak = user.get("daily_streak", 0) + 1
    if daily_streak % 7 == 0:
        reward = 20000
        bonus_text = "🎉 **7-Й ДЕНЬ БОНУС!**"
    else:
        reward = 5000
        bonus_text = "📅 Обычный день"
    
    user["balance"] += reward
    user["last_daily"] = current_time
    user["daily_streak"] = daily_streak
    user["total_earned"] += reward
    
    bot_data.save_data()
    
    days_to_bonus = 7 - (daily_streak % 7)
    if days_to_bonus == 0:
        days_to_bonus = 7
    
    message = f"""
{bonus_text}
🎁 Ежедневная награда: +{reward}💰

📊 Прогресс:
├─ Текущая серия: {daily_streak} дней
├─ До бонуса (20000💰): {days_to_bonus} дней
└─ 💳 Баланс: {user['balance']}💰

💡 Заходите каждый день для увеличения награды!
    """
    
    update.message.reply_text(message)

def transfer(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    if len(context.args) != 2:
        update.message.reply_text(
            "💸 Перевод денег\n\n"
            "Использование: /transfer [@username/ID] [сумма]\n\n"
            "Примеры:\n"
            "/transfer @username 1000\n"
            "/transfer 123456789 500"
        )
        return
    
    target_input = context.args[0]
    try:
        amount = int(context.args[1])
    except ValueError:
        update.message.reply_text("❌ Сумма должна быть числом")
        return
    
    if amount <= 0:
        update.message.reply_text("❌ Сумма должна быть положительной")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    user = bot_data.users[user_id]
    
    if user["balance"] < amount:
        update.message.reply_text("❌ Недостаточно средств")
        return
    
    target_user = None
    
    if target_input.isdigit():
        target_id = int(target_input)
        if target_id in bot_data.users:
            target_user = bot_data.users[target_id]
    
    if not target_user and target_input.startswith('@'):
        found_users = bot_data.search_user_by_username(target_input[1:])
        if found_users:
            target_id, target_user = found_users[0]
    
    if not target_user:
        found_users = bot_data.search_user_by_username(target_input)
        if found_users:
            target_id, target_user = found_users[0]
    
    if not target_user:
        update.message.reply_text("❌ Пользователь не найден")
        return
    
    if target_id == user_id:
        update.message.reply_text("❌ Нельзя переводить самому себе")
        return
    
    if bot_data.is_banned(target_id):
        update.message.reply_text("❌ Нельзя переводить забаненному пользователю")
        return
    
    user["balance"] -= amount
    target_user["balance"] += amount
    
    bot_data.save_data()
    
    try:
        context.bot.send_message(
            chat_id=target_id,
            text=f"💸 Вам перевели {amount}💰 от @{user['username']}"
        )
    except Exception:
        pass
    
    update.message.reply_text(
        f"✅ Успешный перевод!\n"
        f"👤 Получатель: @{target_user['username']}\n"
        f"💰 Сумма: {amount}💰\n"
        f"💳 Ваш остаток: {user['balance']}💰"
    )

def regbank(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    if not context.args:
        update.message.reply_text(
            "🏦 Создание банковского счета\n\n"
            "Использование: /regbank [название счета]\n\n"
            "Пример: /regbank Основной\n"
            "💡 Можно создать до 3 счетов"
        )
        return
    
    account_name = ' '.join(context.args)
    bot_data.init_user(user_id, update.effective_user.username)
    
    result = bot_data.create_bank_account(user_id, account_name)
    update.message.reply_text(result)

def bank(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    user = bot_data.users[user_id]
    
    if len(context.args) != 3:
        update.message.reply_text(
            "🏦 Управление банковскими счетами\n\n"
            "Использование: /bank [номер счета] [сумма] [действие]\n\n"
            "Действия:\n"
            "• deposit - положить деньги\n"
            "• withdraw - забрать деньги\n\n"
            "Примеры:\n"
            "/bank 1 1000 deposit\n"
            "/bank 2 500 withdraw\n\n"
            "💡 Используйте /infobank для просмотра счетов"
        )
        return
    
    try:
        account_index = int(context.args[0]) - 1
        amount = int(context.args[1])
        action = context.args[2].lower()
    except ValueError:
        update.message.reply_text("❌ Номер счета и сумма должны быть числами")
        return
    
    if action == "deposit":
        result = bot_data.bank_deposit(user_id, account_index, amount)
    elif action == "withdraw":
        result = bot_data.bank_withdraw(user_id, account_index, amount)
    else:
        result = "❌ Неверное действие. Используйте 'deposit' или 'withdraw'"
    
    update.message.reply_text(result)

def infobank(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    user = bot_data.users[user_id]
    
    if "bank_accounts" not in user or not user["bank_accounts"]:
        update.message.reply_text(
            "🏦 У вас нет банковских счетов\n\n"
            "Создайте счет командой:\n"
            "/regbank [название счета]\n\n"
            "💡 Можно создать до 3 счетов"
        )
        return
    
    total_bank = sum(account["balance"] for account in user["bank_accounts"])
    
    accounts_text = "🏦 **ВАШИ БАНКОВСКИЕ СЧЕТА**\n\n"
    
    for i, account in enumerate(user["bank_accounts"], 1):
        accounts_text += f"{i}. **{account['name']}**\n"
        accounts_text += f"   💰 Баланс: {account['balance']}\n\n"
    
    accounts_text += f"💳 **Основной баланс:** {user['balance']}💰\n"
    accounts_text += f"🏦 **Всего в банке:** {total_bank}💰\n"
    accounts_text += f"💰 **Общая сумма:** {user['balance'] + total_bank}💰\n\n"
    accounts_text += "💡 Используйте /bank для управления счетами"
    
    update.message.reply_text(accounts_text, parse_mode='Markdown')

def backup(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_creator_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    try:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_data = {
            'users': bot_data.users,
            'banned_users': list(bot_data.banned_users),
            'admin_logs': bot_data.admin_logs,
            'global_multiplier': bot_data.global_multiplier,
            'game_statistics': bot_data.game_statistics,
            'backup_timestamp': timestamp,
            'total_users': len(bot_data.users)
        }
        
        update.message.reply_text(
            f"✅ **Резервная копия создана**\n\n"
            f"📊 Статистика бэкапа:\n"
            f"• 👥 Пользователей: {len(bot_data.users)}\n"
            f"• 🚫 Забанено: {len(bot_data.banned_users)}\n"
            f"• 📝 Логов: {len(bot_data.admin_logs)}\n"
            f"• 🎮 Активных игр: {len(bot_data.game_statistics)}\n"
            f"• ⏰ Время: {timestamp}"
        )
        
    except Exception as e:
        update.message.reply_text(f"❌ Ошибка при создании бэкапа: {e}")

def globalstats(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_creator_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    stats = bot_data.get_bot_stats()
    game_stats = bot_data.get_game_stats()
    
    total_bank_money = 0
    users_with_bank = 0
    for user_data in bot_data.users.values():
        if "bank_accounts" in user_data:
            user_bank = sum(account["balance"] for account in user_data["bank_accounts"])
            total_bank_money += user_bank
            if user_bank > 0:
                users_with_bank += 1
    
    response = "🌍 **ГЛОБАЛЬНАЯ СТАТИСТИКА**\n\n"
    
    response += "📊 **Основная статистика:**\n"
    response += f"• 👥 Всего пользователей: {stats['total_users']}\n"
    response += f"• 🎮 Всего игр сыграно: {stats['total_games']}\n"
    response += f"• 💰 Общий баланс: {stats['total_balance']}\n"
    response += f"• 🏆 Всего заработано: {stats['total_earned']}\n"
    response += f"• 🚫 Забанено: {stats['banned_users']}\n"
    response += f"• 🔧 Администраторов: {stats['active_admins']}\n\n"
    
    response += "🏦 **Банковская статистика:**\n"
    response += f"• 💰 Всего в банках: {total_bank_money}\n"
    response += f"• 👤 Пользователей с вкладами: {users_with_bank}\n"
    response += f"• 💳 Общая денежная масса: {stats['total_balance'] + total_bank_money}\n\n"
    
    response += "🎮 **Статистика по играм:**\n"
    for game_id, game_data in game_stats.items():
        game_name = bot_data.games[game_id]["name"]
        win_rate = (game_data['total_wins'] / game_data['plays'] * 100) if game_data['plays'] > 0 else 0
        response += f"• {game_name}: {game_data['plays']} игр ({win_rate:.1f}% побед)\n"
    
    response += f"\n🎯 Глобальный множитель: {bot_data.global_multiplier}x"
    
    update.message.reply_text(response)

def givepc(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_creator_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if len(context.args) != 2:
        update.message.reply_text(
            "🎯 Выдача PlayCoin\n\n"
            "Использование: /givepc [ID] [количество]\n\n"
            "Пример: /givepc 123456789 100"
        )
        return
    
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        update.message.reply_text("❌ Ошибка: ID и количество должны быть числами")
        return
    
    if target_id not in bot_data.users:
        update.message.reply_text("❌ Пользователь не найден")
        return
    
    if amount <= 0:
        update.message.reply_text("❌ Количество должно быть положительным")
        return
    
    bot_data.users[target_id]["play_coins"] += amount
    
    target_username = bot_data.users[target_id]["username"] or str(target_id)
    bot_data.add_admin_log(user_id, update.effective_user.username or str(user_id), 
                          "ВЫДАЧА_PLAYCOIN", target_username, f"{amount} PC")
    
    update.message.reply_text(
        f"✅ Пользователю {target_username} выдано {amount} PlayCoin\n"
        f"🎯 Теперь у него: {bot_data.users[target_id]['play_coins']} PC"
    )

def start(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены и не можете использовать бота.")
        return
    
    bot_data.init_user(user_id, user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
    welcome_text = bot_data.welcome_message or "🎰 Добро пожаловать в казино-бот!"
    
    if bot_data.is_creator(user_id):
        if not bot_data.is_creator_authenticated(user_id):
            update.message.reply_text(
                f"👑 Добро пожаловать, СОЗДАТЕЛЬ!\n"
                f"{welcome_text}\n\n"
                f"👤 Ваш username: @{user.username}\n"
                f"🆔 Ваш ID: `{user_id}`\n\n"
                f"🔐 Авторизуйтесь: /register [пароль]\n\n"
                f"📋 Основные команды:\n"
                f"/play [ставка] [игра] - сыграть в игру\n"
                f"/balance - ваш баланс\n"
                f"/daily - ежедневная награда\n"
                f"/help - все команды",
                parse_mode='Markdown'
            )
        else:
            update.message.reply_text(
                f"👑 Добро пожаловать, СОЗДАТЕЛЬ!\n"
                f"{welcome_text}\n\n"
                f"👤 Ваш username: @{user.username}\n"
                f"🆔 Ваш ID: `{user_id}`\n\n"
                f"💎 Вам доступны бесконечные монеты и PlayCoin!\n\n"
                f"📋 Основные команды:\n"
                f"/play [ставка] [игра] - сыграть в игру\n"
                f"/balance - ваш баланс\n"
                f"/daily - ежедневная награда\n"
                f"/help - все команды\n\n"
                f"⚙️ Команды создателя: /creatorcmd",
                parse_mode='Markdown'
            )
    
    elif bot_data.users[user_id].get("is_admin", False):
        if not bot_data.is_admin_authenticated(user_id):
            update.message.reply_text(
                f"🔧 Добро пожаловать, Администратор!\n"
                f"{welcome_text}\n\n"
                f"👤 Ваш ID: `{user_id}`\n\n"
                f"🔐 Авторизуйтесь: /panel [пароль]\n\n"
                f"📋 Основные команды:\n"
                f"/play [ставка] [игра] - сыграть в игру\n"
                f"/balance - ваш баланс\n"
                f"/daily - ежедневная награда\n"
                f"/help - все команды",
                parse_mode='Markdown'
            )
        else:
            update.message.reply_text(
                f"🔧 Добро пожаловать, Администратор!\n"
                f"{welcome_text}\n\n"
                f"👤 Ваш ID: `{user_id}`\n\n"
                f"📋 Основные команды:\n"
                f"/play [ставка] [игра] - сыграть в игру\n"
                f"/balance - ваш баланс\n"
                f"/daily - ежедневная награда\n"
                f"/help - все команды\n\n"
                f"⚙️ Команды администратора:\n"
                f"/givecash, /givedonate, /ban, /unban\n"
                f"/search, /announce, /userinfo, /message\n"
                f"/setdonate",
                parse_mode='Markdown'
            )
    
    else:
        update.message.reply_text(
            f"{welcome_text}\n\n"
            f"👤 Ваш ID: `{user_id}`\n\n"
            f"📋 Основные команды:\n"
            f"/play [ставка] [игра] - сыграть в игру\n"
            f"/balance - ваш баланс\n"
            f"/daily - ежедневная награда\n"
            f"/help - все команды\n"
            f"/q [сообщение] - ответить администрации",
            parse_mode='Markdown'
        )

def play(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
    if len(context.args) != 2:
        update.message.reply_text(
            "🎮 Сыграть в игру\n\n"
            "Использование: /play [ставка] [номер игры]\n\n"
            "🎮 Доступные игры:\n"
            "1. 🎡 Рулетка (1-36)\n"
            "2. 🎯 Координаты\n"
            "3. 🪙 Монетка\n"
            "4. 🍀 Удача (50/50 шанс выиграть x2)\n\n"
            "Пример: /play 100 4"
        )
        return

    try:
        bet = int(context.args[0])
        game_id = int(context.args[1])
    except ValueError:
        update.message.reply_text("❌ Ошибка: ставка и номер игры должны быть числами")
        return

    if game_id not in bot_data.games:
        update.message.reply_text("❌ Ошибка: игра не найдена")
        return

    user = bot_data.users[user_id]
    is_creator = bot_data.is_creator(user_id)
    
    if not is_creator and bet > user["balance"]:
        update.message.reply_text("❌ Недостаточно средств")
        return

    if bet <= 0:
        update.message.reply_text("❌ Ставка должна быть положительной")
        return

    bot_data.game_statistics[game_id]["plays"] += 1
    bot_data.game_statistics[game_id]["total_bets"] += bet

    if not is_creator:
        user["balance"] -= bet
    
    user["games_played"] += 1

    result_text = ""
    win_amount = 0
    won = False

    if game_id == 1:
        user_number = random.randint(1, 36)
        win_number = random.randint(1, 36)
        if user_number == win_number:
            win_amount = bet * 36
            won = True
            result_text = f"🎉 Поздравляем! Вы угадали число {win_number} и выиграли {win_amount}!"
        else:
            result_text = f"❌ Вы проиграли. Ваше число: {user_number}, выпало: {win_number}"

    elif game_id == 2:
        user_x, user_y = random.randint(1, 10), random.randint(1, 10)
        target_x, target_y = random.randint(1, 10), random.randint(1, 10)
        distance = abs(user_x - target_x) + abs(user_y - target_y)
        
        if distance == 0:
            win_amount = bet * 10
            won = True
            result_text = f"🎉 Прямое попадание! Выигрыш: {win_amount}"
        elif distance <= 2:
            win_amount = bet * 3
            won = True
            result_text = f"✅ Близко! Дистанция: {distance}. Выигрыш: {win_amount}"
        else:
            result_text = f"❌ Мимо. Ваши координаты: ({user_x},{user_y}), цель: ({target_x},{target_y})"

    elif game_id == 3:
        user_choice = random.choice(["орёл", "решка"])
        result = random.choice(["орёл", "решка"])
        if user_choice == result:
            win_amount = bet * 2
            won = True
            result_text = f"🎉 {result.capitalize()}! Вы угадали и выиграли {win_amount}!"
        else:
            result_text = f"❌ {result.capitalize()}! Вы проиграли."

    elif game_id == 4:
        if random.choice([True, False]):
            win_amount = bet * 2
            won = True
            result_text = f"🍀 Поздравляем! Вам повезло! Вы выиграли {win_amount}!"
        else:
            result_text = f"💔 К сожалению, удача не на вашей стороне. Вы проиграли {bet}."

    if won:
        user["last_win"] = True
        user["win_streak"] += 1
        bot_data.game_statistics[game_id]["total_wins"] += 1
        
        if user["win_streak"] >= 2:
            play_coins_earned = 5
            user["play_coins"] += play_coins_earned
            result_text += f"\n🎯 Страйк {user['win_streak']} побед! +{play_coins_earned} PlayCoin"
    else:
        user["last_win"] = False
        user["win_streak"] = 0

    if win_amount > 0:
        bonus_win = bot_data.check_privilege_bonus(user_id, win_amount)
        if bonus_win > win_amount:
            result_text += f"\n🎁 Бонус: +{bonus_win - win_amount}"
            win_amount = bonus_win
        
        if not is_creator:
            user["balance"] += win_amount
            user["total_earned"] += win_amount

    if not is_creator:
        user["balance"] = max(0, user["balance"])
    
    result_text += f"\n\n💰 Ваш баланс: {'∞' if is_creator else user['balance']}"
    result_text += f"\n🎯 PlayCoin: {'∞' if is_creator else user['play_coins']}"
    result_text += f"\n🔥 Серия побед: {user['win_streak']}"
    
    bot_data.save_data()
    update.message.reply_text(result_text)

def shop(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
    user = bot_data.users[user_id]
    keyboard = []
    
    for priv_id, priv_info in bot_data.privileges.items():
        status = "✅" if user["privilege"] == priv_id else "🔒"
        cost = priv_info["cost"]
        bonus = int((priv_info["bonus"] - 1) * 100)
        title = priv_info["title"]
        
        button_text = f"{status} {title} - {cost} 💰 (+{bonus}%)"
        callback_data = f"buy_{priv_id}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        f"🏪 Магазин привилегий\n\n"
        f"💰 Баланс: {'∞' if bot_data.is_creator(user_id) else user['balance']}\n"
        f"🎯 PlayCoin: {'∞' if bot_data.is_creator(user_id) else user['play_coins']}\n"
        f"👑 Привилегия: {bot_data.privileges[user['privilege']]['title'] if user['privilege'] else 'Нет'}",
        reply_markup=reply_markup
    )

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    user_id = query.from_user.id
    
    if bot_data.is_banned(user_id):
        query.edit_message_text("❌ Вы забанены.")
        return
    
    data = query.data
    
    if data.startswith("buy_"):
        priv_id = data[4:]
        buy_privilege(user_id, priv_id, query)

def buy_privilege(user_id: int, priv_id: str, query):
    if priv_id not in bot_data.privileges:
        query.edit_message_text("❌ Ошибка: привилегия не найдена")
        return
    
    user = bot_data.users[user_id]
    priv_info = bot_data.privileges[priv_id]
    
    if not bot_data.is_creator(user_id) and user["balance"] < priv_info["cost"]:
        query.edit_message_text("❌ Недостаточно средств")
        return
    
    if not bot_data.is_creator(user_id):
        user["balance"] -= priv_info["cost"]
    
    user["privilege"] = priv_id
    
    bot_data.save_data()
    query.edit_message_text(
        f"🎉 Поздравляем с покупкой!\n"
        f"Теперь у вас: {priv_info['title']}\n"
        f"Бонус: +{int((priv_info['bonus'] - 1) * 100)}% к выигрышам\n\n"
        f"💰 Остаток: {'∞' if bot_data.is_creator(user_id) else user['balance']}"
    )

def leaderboard(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    leaderboard_data = bot_data.get_leaderboard()
    
    if not leaderboard_data:
        update.message.reply_text("📊 Пока нет данных для таблицы лидеров")
        return
    
    text = "🏆 ТОП-10 ИГРОКОВ 🏆\n\n"
    
    for i, (user_id, user_data) in enumerate(leaderboard_data, 1):
        username = f"@{user_data['username']}" if user_data["username"] else f"ID: {user_id}"
        privilege_title = ""
        if user_data["privilege"]:
            privilege_title = bot_data.privileges[user_data["privilege"]]["title"]
        
        text += f"{i}. {username} {privilege_title}\n"
        text += f"   💰 Заработано: {user_data['total_earned']}\n\n"
    
    update.message.reply_text(text)

def stats(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
    user = bot_data.users[user_id]
    privilege_title = "Нет"
    if user["privilege"]:
        privilege_title = bot_data.privileges[user["privilege"]]["title"]
    
    donate_info = "Нет"
    if user["exclusive_donate"]:
        donate_desc = bot_data.exclusive_donates[user["exclusive_donate"]]["description"]
        donate_info = f"{user['exclusive_donate']} ({donate_desc})"
    
    role = ""
    if bot_data.is_creator(user_id):
        role = "👑 Создатель"
    elif user.get("is_admin", False):
        role = "🔧 Главный Администратор"
    
    update.message.reply_text(
        f"📊 Ваша статистика {role}\n\n"
        f"👤 ID: `{user_id}`\n"
        f"👤 Username: @{user['username']}\n"
        f"💰 Баланс: {'∞' if bot_data.is_creator(user_id) else user['balance']}\n"
        f"🎯 PlayCoin: {'∞' if bot_data.is_creator(user_id) else user['play_coins']}\n"
        f"👑 Привилегия: {privilege_title}\n"
        f"💎 Эксклюзивный донат: {donate_info}\n"
        f"🎮 Сыграно игр: {user['games_played']}\n"
        f"🏆 Всего заработано: {user['total_earned']}\n"
        f"🔥 Текущая серия побед: {user['win_streak']}",
        parse_mode='Markdown'
    )

def promo(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
    if not context.args:
        update.message.reply_text("Использование: /promo [код]")
        return
    
    code = context.args[0]
    result = bot_data.activate_promo_code(user_id, code)
    update.message.reply_text(result, parse_mode='Markdown')

def repriv(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
    if not context.args:
        update.message.reply_text(
            "👑 Сменить привилегию\n\n"
            "Использование: /repriv [название]\n\n"
            "👑 Доступные привилегии:\n"
            "• bronze, silver, gold, platinum\n\n"
            "💎 Доступные донаты:\n"
            "• TITAN, FLE, DRAGON"
        )
        return
    
    new_privilege = context.args[0].lower()
    result = bot_data.change_privilege(user_id, new_privilege)
    update.message.reply_text(result)

def register(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_creator(user_id):
        update.message.reply_text("❌ Эта команда доступна только создателю бота")
        return
    
    if bot_data.is_creator_authenticated(user_id):
        update.message.reply_text("✅ Вы уже авторизованы как создатель")
        return
    
    if not context.args:
        update.message.reply_text("🔐 Авторизуйтесь: /register [пароль]")
        return
    
    password = context.args[0]
    
    if password == bot_data.creator_password:
        bot_data.users[user_id]["creator_authenticated"] = True
        bot_data.users[user_id]["creator_auth_time"] = time.time()
        bot_data.save_data()
        update.message.reply_text(
            "✅ Авторизация успешна! Теперь вам доступны все команды создателя.\n\n"
            "💡 Авторизация действует 24 часа\n"
            "📋 Используйте /creatorcmd для просмотра команд"
        )
    else:
        update.message.reply_text("❌ Неверный пароль")

def panel(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_admin(user_id):
        update.message.reply_text("❌ Эта команда доступна только администраторам")
        return
    
    if bot_data.is_admin_authenticated(user_id):
        update.message.reply_text("✅ Вы уже авторизованы как администратор")
        return
    
    if user_id not in bot_data.admin_passwords:
        if not context.args:
            update.message.reply_text("🔐 Создайте пароль для авторизации. Пример: /panel 123892hdi8738")
            return
        
        password = context.args[0]
        bot_data.admin_passwords[user_id] = password
        bot_data.save_data()
        update.message.reply_text(
            f"✅ Пароль установлен! Теперь авторизуйтесь: /panel {password}\n\n"
            f"💡 Авторизация действует 24 часа"
        )
        return
    
    if not context.args:
        update.message.reply_text("🔐 Авторизуйтесь: /panel [ваш пароль]")
        return
    
    password = context.args[0]
    
    if user_id in bot_data.admin_passwords and bot_data.admin_passwords[user_id] == password:
        bot_data.users[user_id]["admin_authenticated"] = True
        bot_data.users[user_id]["admin_auth_time"] = time.time()
        bot_data.save_data()
        update.message.reply_text(
            "✅ Авторизация успешна! Теперь вам доступны команды администратора.\n\n"
            "💡 Авторизация действует 24 часа"
        )
    else:
        update.message.reply_text("❌ Неверный пароль")

def creatorcmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_creator(user_id):
        update.message.reply_text("❌ Эта команда доступна только создателю бота")
        return
    
    if not bot_data.is_creator_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    commands_list = [
        "👑 КОМАНДЫ СОЗДАТЕЛЯ:\n",
        "💰 ЭКОНОМИКА:",
        "/setbalance [ID] [сумма] - установить баланс пользователю",
        "/reseteconomy - полный сброс экономики",
        "/setmultiplier [значение] - установить глобальный множитель",
        "/massgive [сумма] [критерий] - массовая выдача монет",
        "",
        "👤 УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ:",
        "/resetuser [ID] - сбросить статистику пользователя",
        "/setgladmin [@username] - назначить главного администратора",
        "/cleanup [дни] - удалить неактивных пользователей",
        "",
        "🎮 УПРАВЛЕНИЕ ИГРАМИ:",
        "/addgame [название] [описание] - добавить новую игру",
        "/gamestats - детальная статистика игр",
        "",
        "⚙️ СИСТЕМНЫЕ КОМАНДЫ:",
        "/botstats - статистика бота",
        "/exportdata - экспорт данных пользователей",
        "/topactive [лимит] - топ активных игроков",
        "/listadmins - список администраторов",
        "/logs - логи администраторов",
        "/setwelcome [текст] - установить приветствие",
        "/createpromo - создать промокод",
        "/testmode [on/off] - тестовый режим",
        "/massprivilege [привилегия] - массовая выдача привилегии",
        "/reboot - перезагрузка бота",
        "",
        "📨 КОММУНИКАЦИЯ:",
        "/announce [текст] - глобальная рассылка",
        "/message [ID] [текст] - отправить сообщение пользователю",
        "",
        "🎁 ДОПОЛНИТЕЛЬНО:",
        "/setdonate [ID] [донат] - выдать эксклюзивный донат",
        "/backup - создать резервную копию",
        "/globalstats - глобальная статистика",
        "/givepc [ID] [количество] - выдать PlayCoin"
    ]
    
    update.message.reply_text("\n".join(commands_list))

def q(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    if not context.args:
        update.message.reply_text(
            "💬 Ответить создателю/администратору\n\n"
            "Использование: /q [текст сообщения]\n\n"
            "⚠️ Можно использовать 1 раз каждые 5 минут"
        )
        return
    
    can_reply, message = bot_data.can_user_reply(user_id)
    if not can_reply:
        update.message.reply_text(message)
        return
    
    message_text = ' '.join(context.args)
    user_data = bot_data.users.get(user_id, {})
    username = user_data.get("username", "Неизвестно")
    
    bot_data.last_reply_time[user_id] = time.time()
    bot_data.save_data()
    
    sent_count = 0
    for admin_id, admin_data in bot_data.users.items():
        if bot_data.is_admin(admin_id):
            try:
                context.bot.send_message(
                    chat_id=admin_id,
                    text=f"💬 Ответ от пользователя:\n"
                         f"👤 ID: {user_id}\n"
                         f"📛 Username: @{username}\n\n"
                         f"💭 Сообщение: {message_text}"
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение администратору {admin_id}: {e}")
    
    if sent_count > 0:
        update.message.reply_text("✅ Ваше сообщение отправлено!")
    else:
        update.message.reply_text("❌ В данный момент нет активных администраторов")

def announce(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_admin_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как администратор: /panel [пароль]")
        return
    
    if not context.args:
        update.message.reply_text(
            "📢 Глобальная рассылка сообщения\n\n"
            "Использование: /announce [текст сообщения]\n\n"
            "💡 Пользователи смогут ответить командой /q"
        )
        return
    
    message = ' '.join(context.args)
    sender_role = "Создателя" if bot_data.is_creator(user_id) else "Администратора"
    
    sent_count = 0
    failed_count = 0
    
    users_to_notify = list(bot_data.users.items())[:100]
    
    for target_id, user_data in users_to_notify:
        try:
            context.bot.send_message(
                chat_id=target_id,
                text=f"📢 Сообщение от {sender_role}:\n\n{message}\n\n"
                     f"💬 Ответить: /q [ваше сообщение]"
            )
            sent_count += 1
            time.sleep(0.1)
        except Exception as e:
            failed_count += 1
            logging.error(f"Не удалось отправить сообщение пользователю {target_id}: {e}")
    
    update.message.reply_text(
        f"✅ Рассылка завершена:\n"
        f"• Отправлено: {sent_count}\n"
        f"• Не удалось: {failed_count}\n"
        f"• Всего пользователей в базе: {len(bot_data.users)}"
    )

def setdonate(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_admin_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как администратор: /panel [пароль]")
        return
    
    if len(context.args) != 2:
        update.message.reply_text(
            "🎁 Выдача эксклюзивного доната\n\n"
            "Использование: /setdonate [ID пользователя] [название доната]\n\n"
            "💎 Доступные донаты:\n"
            "• TITAN - x10 монет при выигрыше\n"
            "• FLE - x20 монет при выигрыше\n" 
            "• DRAGON - x50 монет + 1 прокрутка колеса\n\n"
            "Пример: /setdonate 123456789 TITAN"
        )
        return
    
    try:
        target_id = int(context.args[0])
        donate_name = context.args[1].upper()
    except ValueError:
        update.message.reply_text("❌ Ошибка: ID должен быть числом")
        return
    
    if target_id not in bot_data.users:
        update.message.reply_text("❌ Пользователь не найден")
        return
    
    if donate_name not in bot_data.exclusive_donates:
        update.message.reply_text("❌ Неверное название доната. Доступные: TITAN, FLE, DRAGON")
        return
    
    bot_data.users[target_id]["exclusive_donate"] = donate_name
    donate_desc = bot_data.exclusive_donates[donate_name]["description"]
    
    if not bot_data.is_creator(user_id):
        admin_username = update.effective_user.username or str(user_id)
        target_username = bot_data.users[target_id]["username"] or str(target_id)
        bot_data.add_admin_log(user_id, admin_username, "ВЫДАЧА_ДОНАТА", target_username, donate_name)
    
    update.message.reply_text(
        f"✅ Пользователю {target_id} выдан донат {donate_name}\n"
        f"📝 {donate_desc}"
    )

def message_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_admin_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как администратор: /panel [пароль]")
        return
    
    if len(context.args) < 2:
        update.message.reply_text(
            "📨 Отправка сообщения пользователю\n\n"
            "Использование: /message [ID пользователя] [текст сообщения]\n\n"
            "Пример: /message 123456789 Привет! Как дела?"
        )
        return
    
    try:
        target_id = int(context.args[0])
        message_text = ' '.join(context.args[1:])
    except ValueError:
        update.message.reply_text("❌ Ошибка: ID должен быть числом")
        return
    
    if target_id not in bot_data.users:
        update.message.reply_text("❌ Пользователь не найден")
        return
    
    try:
        sender_role = "Создателя" if bot_data.is_creator(user_id) else "Администратора"
        context.bot.send_message(
            chat_id=target_id,
            text=f"📨 Сообщение от {sender_role}:\n\n{message_text}"
        )
        update.message.reply_text(f"✅ Сообщение отправлено пользователю {target_id}")
    except Exception as e:
        update.message.reply_text(f"❌ Не удалось отправить сообщение: {e}")

def givecash(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_admin_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как администратор: /panel [пароль]")
        return
    
    if len(context.args) != 2:
        update.message.reply_text("Использование: /givecash [id] [amount]")
        return
    
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        update.message.reply_text("❌ Ошибка: ID и количество должны быть числами")
        return
    
    if target_id not in bot_data.users:
        update.message.reply_text("❌ Пользователь не найден")
        return
    
    bot_data.users[target_id]["balance"] += amount
    
    if not bot_data.is_creator(user_id):
        admin_username = update.effective_user.username or str(user_id)
        target_username = bot_data.users[target_id]["username"] or str(target_id)
        bot_data.add_admin_log(user_id, admin_username, "ВЫДАЧА_МОНЕТ", target_username, f"{amount} монет")
    
    update.message.reply_text(f"✅ Баланс пользователя {target_id} пополнен на {amount}")

def givedonate(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_admin_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как администратор: /panel [пароль]")
        return
    
    if len(context.args) != 2:
        update.message.reply_text("Использование: /givedonate [id] [donate]\nДоступные донаты: TITAN, FLE, DRAGON")
        return
    
    try:
        target_id = int(context.args[0])
        donate_name = context.args[1].upper()
    except ValueError:
        update.message.reply_text("❌ Ошибка: ID должен быть числом")
        return
    
    if target_id not in bot_data.users:
        update.message.reply_text("❌ Пользователь не найден")
        return
    
    if donate_name not in bot_data.exclusive_donates:
        update.message.reply_text("❌ Неверное название доната. Доступные: TITAN, FLE, DRAGON")
        return
    
    bot_data.users[target_id]["exclusive_donate"] = donate_name
    donate_desc = bot_data.exclusive_donates[donate_name]["description"]
    
    if not bot_data.is_creator(user_id):
        admin_username = update.effective_user.username or str(user_id)
        target_username = bot_data.users[target_id]["username"] or str(target_id)
        bot_data.add_admin_log(user_id, admin_username, "ВЫДАЧА_ДОНАТА", target_username, donate_name)
    
    update.message.reply_text(f"✅ Пользователю {target_id} выдан донат {donate_name}\n{donate_desc}")

def ban(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_admin_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как администратор: /panel [пароль]")
        return
    
    if len(context.args) != 1:
        update.message.reply_text("Использование: /ban [id]")
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        update.message.reply_text("❌ Ошибка: ID должен быть числом")
        return
    
    if bot_data.is_creator(target_id):
        update.message.reply_text("❌ Нельзя забанить создателя")
        return
    
    bot_data.banned_users.add(target_id)
    
    if not bot_data.is_creator(user_id):
        admin_username = update.effective_user.username or str(user_id)
        target_username = bot_data.users[target_id]["username"] if target_id in bot_data.users else str(target_id)
        bot_data.add_admin_log(user_id, admin_username, "БАН", target_username)
    
    update.message.reply_text(f"✅ Пользователь {target_id} забанен")

def unban(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_admin_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как администратор: /panel [пароль]")
        return
    
    if len(context.args) != 1:
        update.message.reply_text("Использование: /unban [id]")
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        update.message.reply_text("❌ Ошибка: ID должен быть числом")
        return
    
    if target_id in bot_data.banned_users:
        bot_data.banned_users.remove(target_id)
        
        if not bot_data.is_creator(user_id):
            admin_username = update.effective_user.username or str(user_id)
            target_username = bot_data.users[target_id]["username"] if target_id in bot_data.users else str(target_id)
            bot_data.add_admin_log(user_id, admin_username, "РАЗБАН", target_username)
        
        update.message.reply_text(f"✅ Пользователь {target_id} разбанен")
    else:
        update.message.reply_text("❌ Пользователь не забанен")

def search(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_admin_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как администратор: /panel [пароль]")
        return
    
    if len(context.args) != 1:
        update.message.reply_text("Использование: /search [@username]\nПример: /search @username")
        return
    
    username = context.args[0]
    found_users = bot_data.search_user_by_username(username)
    
    if not found_users:
        update.message.reply_text(f"❌ Пользователь {username} не найден")
        return
    
    response = f"🔍 Найденные пользователи по запросу {username}:\n\n"
    for user_id, user_data in found_users:
        response += f"👤 Username: @{user_data['username']}\n"
        response += f"🆔 ID: `{user_id}`\n"
        response += f"💰 Баланс: {user_data['balance']}\n"
        response += f"🎮 Игр сыграно: {user_data['games_played']}\n"
        response += f"🏆 Заработано: {user_data['total_earned']}\n"
        response += "─" * 30 + "\n"
    
    update.message.reply_text(response, parse_mode='Markdown')

def userinfo(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_admin_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как администратор: /panel [пароль]")
        return
    
    if len(context.args) != 1:
        update.message.reply_text("Использование: /userinfo [id]")
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        update.message.reply_text("❌ Ошибка: ID должен быть числом")
        return
    
    if target_id not in bot_data.users:
        update.message.reply_text("❌ Пользователь не найден")
        return
    
    user_data = bot_data.users[target_id]
    privilege_title = "Нет"
    if user_data["privilege"]:
        privilege_title = bot_data.privileges[user_data["privilege"]]["title"]
    
    donate_info = "Нет"
    if user_data["exclusive_donate"]:
        donate_desc = bot_data.exclusive_donates[user_data["exclusive_donate"]]["description"]
        donate_info = f"{user_data['exclusive_donate']} ({donate_desc})"
    
    role = "👤 Игрок"
    if bot_data.is_creator(target_id):
        role = "👑 СОЗДАТЕЛЬ"
    elif user_data.get("is_admin", False):
        role = "🔧 АДМИНИСТРАТОР"
    
    last_activity = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(user_data.get("last_activity", 0)))
    
    response = f"📋 ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ:\n\n"
    response += f"👤 Username: @{user_data['username']}\n"
    response += f"🆔 ID: {target_id}\n"
    response += f"🎭 Роль: {role}\n"
    response += f"💰 Баланс: {user_data['balance']}\n"
    response += f"🎯 PlayCoin: {user_data['play_coins']}\n"
    response += f"👑 Привилегия: {privilege_title}\n"
    response += f"💎 Донат: {donate_info}\n"
    response += f"🎮 Сыграно игр: {user_data['games_played']}\n"
    response += f"🏆 Всего заработано: {user_data['total_earned']}\n"
    response += f"🔥 Серия побед: {user_data['win_streak']}\n"
    response += f"⏰ Последняя активность: {last_activity}\n"
    response += f"🚫 Статус бана: {'Да' if target_id in bot_data.banned_users else 'Нет'}"
    
    update.message.reply_text(response)

def setbalance(update: Update, context: CallbackContext):
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if len(context.args) != 2:
        update.message.reply_text("Использование: /setbalance [id] [amount]")
        return
    
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        update.message.reply_text("❌ Ошибка: ID и количество должны быть числами")
        return
    
    if target_id not in bot_data.users:
        update.message.reply_text("❌ Пользователь не найден")
        return
    
    bot_data.users[target_id]["balance"] = amount
    bot_data.save_data()
    update.message.reply_text(f"✅ Баланс пользователя {target_id} установлен в {amount}")

def reseteconomy(update: Update, context: CallbackContext):
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    bot_data.reset_economy()
    update.message.reply_text("✅ Экономика бота полностью сброшена!")

def setmultiplier(update: Update, context: CallbackContext):
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if len(context.args) != 1:
        update.message.reply_text("Использование: /setmultiplier [value]")
        return
    
    try:
        multiplier = float(context.args[0])
    except ValueError:
        update.message.reply_text("❌ Ошибка: множитель должен быть числом")
        return
    
    bot_data.global_multiplier = multiplier
    bot_data.save_data()
    update.message.reply_text(f"✅ Глобальный множитель установлен: {multiplier}x")

def resetuser(update: Update, context: CallbackContext):
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if len(context.args) != 1:
        update.message.reply_text("Использование: /resetuser [id]")
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        update.message.reply_text("❌ Ошибка: ID должен быть числом")
        return
    
    if target_id not in bot_data.users:
        update.message.reply_text("❌ Пользователь не найден")
        return
    
    if bot_data.is_creator(target_id):
        update.message.reply_text("❌ Нельзя сбросить статистику создателя")
        return
    
    user_data = bot_data.users[target_id]
    user_data.update({
        "balance": 1000,
        "play_coins": 0,
        "privilege": None,
        "exclusive_donate": None,
        "total_earned": 0,
        "games_played": 0,
        "win_streak": 0,
        "last_win": False
    })
    
    bot_data.save_data()
    update.message.reply_text(f"✅ Статистика пользователя {target_id} сброшена")

def massgive(update: Update, context: CallbackContext):
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if len(context.args) < 2:
        update.message.reply_text("Использование: /massgive [amount] [criteria]\nКритерии: all, with_privilege, no_privilege")
        return
    
    try:
        amount = int(context.args[0])
        criteria = context.args[1].lower()
    except ValueError:
        update.message.reply_text("❌ Ошибка: количество должно быть числом")
        return
    
    if criteria not in ["all", "with_privilege", "no_privilege"]:
        update.message.reply_text("❌ Неверный критерий. Доступно: all, with_privilege, no_privilege")
        return
    
    affected = bot_data.mass_give_coins(amount, criteria)
    update.message.reply_text(f"✅ Выдано {amount} монет {affected} пользователям (критерий: {criteria})")

def listadmins(update: Update, context: CallbackContext):
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    admins = []
    for user_id, user_data in bot_data.users.items():
        if user_data.get("is_admin", False) or bot_data.is_creator(user_id):
            admins.append((user_id, user_data))
    
    if not admins:
        update.message.reply_text("📋 Администраторы не найдены")
        return
    
    response = "👑 АДМИНИСТРАТОРЫ БОТА:\n\n"
    for user_id, user_data in admins:
        role = "👑 СОЗДАТЕЛЬ" if bot_data.is_creator(user_id) else "🔧 АДМИНИСТРАТОР"
        response += f"{role}\n"
        response += f"👤 @{user_data['username']}\n"
        response += f"🆔 ID: {user_id}\n"
        response += f"🎮 Игр: {user_data['games_played']}\n"
        response += "─" * 30 + "\n"
    
    update.message.reply_text(response)

def botstats(update: Update, context: CallbackContext):
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    stats = bot_data.get_bot_stats()
    game_stats = bot_data.get_game_stats()
    
    response = "📊 СТАТИСТИКА БОТА:\n\n"
    response += f"👥 Всего пользователей: {stats['total_users']}\n"
    response += f"🎮 Всего сыграно игр: {stats['total_games']}\n"
    response += f"💰 Общий баланс: {stats['total_balance']}\n"
    response += f"🏆 Всего заработано: {stats['total_earned']}\n"
    response += f"🚫 Забанено: {stats['banned_users']}\n"
    response += f"🔧 Администраторов: {stats['active_admins']}\n"
    response += f"🎯 Глобальный множитель: {bot_data.global_multiplier}x\n\n"
    
    response += "🎮 СТАТИСТИКА ПО ИГРАМ:\n"
    for game_id, game_data in game_stats.items():
        game_name = bot_data.games[game_id]["name"]
        win_rate = (game_data['total_wins'] / game_data['plays'] * 100) if game_data['plays'] > 0 else 0
        response += f"  {game_name}: {game_data['plays']} игр ({win_rate:.1f}% побед)\n"
    
    update.message.reply_text(response)

def exportdata(update: Update, context: CallbackContext):
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if not bot_data.users:
        update.message.reply_text("❌ Нет данных для экспорта")
        return
    
    response = "📁 ЭКСПОРТ ДАННЫХ ПОЛЬЗОВАТЕЛЕЙ (первые 50):\n\n"
    count = 0
    
    for user_id, user_data in list(bot_data.users.items())[:50]:
        if bot_data.is_creator(user_id):
            continue
            
        response += f"👤 @{user_data['username']} (ID: {user_id})\n"
        response += f"💰 Баланс: {user_data['balance']}\n"
        response += f"🎮 Игр: {user_data['games_played']}\n"
        response += f"🏆 Заработано: {user_data['total_earned']}\n"
        response += "─" * 40 + "\n"
        count += 1
        
        if len(response) > 3000:
            break
    
    response += f"\n📊 Всего пользователей в базе: {len(bot_data.users)}"
    update.message.reply_text(response)

def topactive(update: Update, context: CallbackContext):
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    limit = 10
    if context.args and context.args[0].isdigit():
        limit = min(int(context.args[0]), 20)
    
    top_users = bot_data.get_top_active_users(limit)
    
    if not top_users:
        update.message.reply_text("❌ Нет данных о пользователях")
        return
    
    response = f"🏆 ТОП-{limit} АКТИВНЫХ ИГРОКОВ:\n\n"
    for i, (user_id, user_data) in enumerate(top_users, 1):
        response += f"{i}. @{user_data['username']}\n"
        response += f"   🎮 Игр: {user_data['games_played']}\n"
        response += f"   💰 Баланс: {user_data['balance']}\n"
        response += "─" * 30 + "\n"
    
    update.message.reply_text(response)

def gamestats(update: Update, context: CallbackContext):
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    game_stats = bot_data.get_game_stats()
    
    response = "📈 ДЕТАЛЬНАЯ СТАТИСТИКА ИГР:\n\n"
    for game_id, stats in game_stats.items():
        game_name = bot_data.games[game_id]["name"]
        win_rate = (stats['total_wins'] / stats['plays'] * 100) if stats['plays'] > 0 else 0
        
        response += f"🎮 {game_name}:\n"
        response += f"   • Сыграно: {stats['plays']} раз\n"
        response += f"   • Общие ставки: {stats['total_bets']}\n"
        response += f"   • Побед: {stats['total_wins']}\n"
        response += f"   • Win Rate: {win_rate:.1f}%\n\n"
    
    update.message.reply_text(response)

def reboot(update: Update, context: CallbackContext):
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    update.message.reply_text("🔄 Перезагрузка бота...")
    update.message.reply_text("✅ Бот 'перезагружен'. Все данные сохранены.")

def cleanup(update: Update, context: CallbackContext):
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    days = 30
    if context.args and context.args[0].isdigit():
        days = int(context.args[0])
    
    removed_count = bot_data.cleanup_inactive_users(days)
    update.message.reply_text(f"🧹 Удалено {removed_count} неактивных пользователей (неактивность > {days} дней)")

def setwelcome(update: Update, context: CallbackContext):
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if not context.args:
        update.message.reply_text("Использование: /setwelcome [текст приветствия]")
        return
    
    welcome_text = ' '.join(context.args)
    bot_data.welcome_message = welcome_text
    bot_data.save_data()
    update.message.reply_text(f"✅ Приветственное сообщение установлено:\n\n{welcome_text}")

def createpromo(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_creator_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if len(context.args) < 2:
        update.message.reply_text(
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
            update.message.reply_text("Укажите сумму: /createpromo [код] cash [сумма]")
            return
        value = context.args[2]
        bot_data.create_promo_code(code, "cash", value)
        update.message.reply_text(f"✅ Промокод создан: {code}\nНаграда: +{value} монет")
    
    elif reward_type == "multiplier":
        if len(context.args) < 4:
            update.message.reply_text("Укажите множитель и длительность: /createpromo [код] multiplier [множитель] [часы]")
            return
        value = context.args[2]
        duration = int(context.args[3])
        bot_data.create_promo_code(code, "multiplier", value, duration)
        update.message.reply_text(f"✅ Промокод создан: {code}\nНаграда: множитель x{value} на {duration} час(ов)")
    
    elif reward_type == "privilege":
        if len(context.args) < 3:
            update.message.reply_text("Укажите привилегию: /createpromo [код] privilege [bronze/silver/gold/platinum]")
            return
        value = context.args[2].lower()
        if value not in bot_data.privileges:
            update.message.reply_text("❌ Неверная привилегия. Доступно: bronze, silver, gold, platinum")
            return
        bot_data.create_promo_code(code, "privilege", value)
        update.message.reply_text(f"✅ Промокод создан: {code}\nНаграда: привилегия {bot_data.privileges[value]['title']}")
    
    elif reward_type == "donate":
        if len(context.args) < 3:
            update.message.reply_text("Укажите донат: /createpromo [код] donate [TITAN/FLE/DRAGON]")
            return
        value = context.args[2].upper()
        if value not in bot_data.exclusive_donates:
            update.message.reply_text("❌ Неверный донат. Доступно: TITAN, FLE, DRAGON")
            return
        bot_data.create_promo_code(code, "donate", value)
        update.message.reply_text(f"✅ Промокод создан: {code}\nНаграда: донат {value}")
    
    else:
        update.message.reply_text("❌ Неверный тип награды. Доступно: cash, multiplier, privilege, donate")

def testmode(update: Update, context: CallbackContext):
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if not context.args:
        update.message.reply_text(f"🎯 Тестовый режим: {'ВКЛ' if bot_data.test_mode else 'ВЫКЛ'}")
        return
    
    mode = context.args[0].lower()
    if mode in ["on", "вкл", "true", "1"]:
        bot_data.test_mode = True
        bot_data.save_data()
        update.message.reply_text("✅ Тестовый режим ВКЛЮЧЕН")
    elif mode in ["off", "выкл", "false", "0"]:
        bot_data.test_mode = False
        bot_data.save_data()
        update.message.reply_text("✅ Тестовый режим ВЫКЛЮЧЕН")
    else:
        update.message.reply_text("❌ Использование: /testmode [on/off]")

def addgame(update: Update, context: CallbackContext):
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if len(context.args) < 2:
        update.message.reply_text("Использование: /addgame [название] [описание]")
        return
    
    game_name = context.args[0]
    game_description = ' '.join(context.args[1:])
    
    new_game_id = max(bot_data.games.keys()) + 1
    bot_data.games[new_game_id] = {
        "name": game_name,
        "description": game_description
    }
    bot_data.game_statistics[new_game_id] = {
        "plays": 0,
        "total_bets": 0,
        "total_wins": 0
    }
    
    bot_data.save_data()
    update.message.reply_text(f"✅ Новая игра добавлена:\nID: {new_game_id}\nНазвание: {game_name}\nОписание: {game_description}")

def massprivilege(update: Update, context: CallbackContext):
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if len(context.args) != 1:
        update.message.reply_text("Использование: /massprivilege [привилегия]\nДоступно: bronze, silver, gold, platinum")
        return
    
    privilege = context.args[0].lower()
    if privilege not in bot_data.privileges:
        update.message.reply_text("❌ Неверная привилегия. Доступно: bronze, silver, gold, platinum")
        return
    
    affected = 0
    for user_id, user_data in bot_data.users.items():
        if not bot_data.is_creator(user_id):
            user_data["privilege"] = privilege
            affected += 1
    
    privilege_title = bot_data.privileges[privilege]["title"]
    bot_data.save_data()
    update.message.reply_text(f"✅ Привилегия {privilege_title} выдана {affected} пользователям")

def setgladmin(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_creator_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if len(context.args) != 1:
        update.message.reply_text("Использование: /setgladmin [@username]\nПример: /setgladmin @username")
        return
    
    username = context.args[0]
    found_users = bot_data.search_user_by_username(username)
    
    if not found_users:
        update.message.reply_text(f"❌ Пользователь {username} не найден")
        return
    
    target_id, target_data = found_users[0]
    
    bot_data.users[target_id]["is_admin"] = True
    
    admin_username = update.effective_user.username or str(update.effective_user.id)
    bot_data.add_admin_log(user_id, admin_username, "НАЗНАЧЕНИЕ_АДМИНА", target_data["username"])
    
    update.message.reply_text(f"✅ Пользователь @{target_data['username']} теперь Главный Администратор!")

def logs(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_creator_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if not bot_data.admin_logs:
        update.message.reply_text("📝 Логи администраторов пусты.")
        return
    
    response = "📝 ЛОГИ АДМИНИСТРАТОРОВ:\n\n"
    
    for log in reversed(bot_data.admin_logs[-20:]):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(log["timestamp"]))
        admin = f"@{log['admin_username']}" if log['admin_username'] else f"ID:{log['admin_id']}"
        target = f"@{log['target_username']}" if log['target_username'] else ""
        
        action_text = ""
        if log["action"] == "НАЗНАЧЕНИЕ_АДМИНА":
            action_text = f"назначил администратором {target}"
        elif log["action"] == "ВЫДАЧА_МОНЕТ":
            action_text = f"выдал монеты {target} ({log['details']})"
        elif log["action"] == "ВЫДАЧА_ДОНАТА":
            action_text = f"выдал донат {target} ({log['details']})"
        elif log["action"] == "БАН":
            action_text = f"забанил {target}"
        elif log["action"] == "РАЗБАН":
            action_text = f"разбанил {target}"
        
        response += f"⏰ {timestamp}\n"
        response += f"👤 {admin} {action_text}\n"
        response += "─" * 40 + "\n"
    
    update.message.reply_text(response)

def author(update: Update, context: CallbackContext):
    update.message.reply_text("👨‍💻 Автор бота: Frapello")

def wheel(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
    result = bot_data.spin_wheel(user_id)
    user = bot_data.users[user_id]
    
    result_text = f"{result}\n\n🎯 Осталось PlayCoin: {'∞' if bot_data.is_creator(user_id) else user['play_coins']}"
    update.message.reply_text(result_text)

def main():
    if not TOKEN:
        logger.error("❌ Токен не найден! Установите переменную TELEGRAM_TOKEN")
        return
    
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    
    # Основные команды для всех
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("play", play))
    dispatcher.add_handler(CommandHandler("shop", shop))
    dispatcher.add_handler(CommandHandler("leaderboard", leaderboard))
    dispatcher.add_handler(CommandHandler("stats", stats))
    dispatcher.add_handler(CommandHandler("author", author))
    dispatcher.add_handler(CommandHandler("wheel", wheel))
    dispatcher.add_handler(CommandHandler("promo", promo))
    dispatcher.add_handler(CommandHandler("repriv", repriv))
    dispatcher.add_handler(CommandHandler("q", q))
    
    # Новые команды для пользователей
    dispatcher.add_handler(CommandHandler("help", help_cmd))
    dispatcher.add_handler(CommandHandler("balance", balance))
    dispatcher.add_handler(CommandHandler("daily", daily))
    dispatcher.add_handler(CommandHandler("transfer", transfer))
    dispatcher.add_handler(CommandHandler("regbank", regbank))
    dispatcher.add_handler(CommandHandler("bank", bank))
    dispatcher.add_handler(CommandHandler("infobank", infobank))
    
    # Команды авторизации
    dispatcher.add_handler(CommandHandler("register", register))
    dispatcher.add_handler(CommandHandler("panel", panel))
    dispatcher.add_handler(CommandHandler("creatorcmd", creatorcmd))
    
    # Новые команды для создателя
    dispatcher.add_handler(CommandHandler("backup", backup))
    dispatcher.add_handler(CommandHandler("globalstats", globalstats))
    dispatcher.add_handler(CommandHandler("givepc", givepc))
    
    # Существующие команды
    dispatcher.add_handler(CommandHandler("setdonate", setdonate))
    dispatcher.add_handler(CommandHandler("message", message_cmd))
    dispatcher.add_handler(CommandHandler("givecash", givecash))
    dispatcher.add_handler(CommandHandler("givedonate", givedonate))
    dispatcher.add_handler(CommandHandler("ban", ban))
    dispatcher.add_handler(CommandHandler("unban", unban))
    dispatcher.add_handler(CommandHandler("search", search))
    dispatcher.add_handler(CommandHandler("userinfo", userinfo))
    dispatcher.add_handler(CommandHandler("announce", announce))
    dispatcher.add_handler(CommandHandler("setbalance", setbalance))
    dispatcher.add_handler(CommandHandler("reseteconomy", reseteconomy))
    dispatcher.add_handler(CommandHandler("setmultiplier", setmultiplier))
    dispatcher.add_handler(CommandHandler("resetuser", resetuser))
    dispatcher.add_handler(CommandHandler("massgive", massgive))
    dispatcher.add_handler(CommandHandler("listadmins", listadmins))
    dispatcher.add_handler(CommandHandler("botstats", botstats))
    dispatcher.add_handler(CommandHandler("exportdata", exportdata))
    dispatcher.add_handler(CommandHandler("topactive", topactive))
    dispatcher.add_handler(CommandHandler("gamestats", gamestats))
    dispatcher.add_handler(CommandHandler("reboot", reboot))
    dispatcher.add_handler(CommandHandler("cleanup", cleanup))
    dispatcher.add_handler(CommandHandler("setwelcome", setwelcome))
    dispatcher.add_handler(CommandHandler("createpromo", createpromo))
    dispatcher.add_handler(CommandHandler("testmode", testmode))
    dispatcher.add_handler(CommandHandler("addgame", addgame))
    dispatcher.add_handler(CommandHandler("massprivilege", massprivilege))
    dispatcher.add_handler(CommandHandler("setgladmin", setgladmin))
    dispatcher.add_handler(CommandHandler("logs", logs))
    
    dispatcher.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("🤖 Бот запущен и работает 24/7!")
    logger.info("💾 Система сохранения данных активирована")
    logger.info("🏦 Банковская система добавлена")
    logger.info("👑 Создатель бота: Frapello")
    
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
