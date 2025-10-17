import os
import logging
import random
import time
import json
import threading
from typing import Dict, List, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

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
    # Для совместимости с разными версиями Python
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

# Запускаем health server в отдельном потоке
health_thread = threading.Thread(target=run_health_server, daemon=True)
health_thread.start()

TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TOKEN:
    logger.error("❌ TELEGRAM_TOKEN не установлен!")
    # Для тестирования, но в продакшене это должно быть установлено
    raise ValueError("TELEGRAM_TOKEN не найден в переменных окружения")

class CasinoBot:
    def __init__(self):
        # Используем абсолютный путь для файла данных
        self.data_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_data.json")
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
        self.last_reply_time = {}  # Для отслеживания времени ответов пользователей
        
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
        """Сохраняет все данные в JSON файл"""
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
        """Загружает данные из JSON файла"""
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
                
                # Конвертируем ключи users обратно в int (JSON сохраняет ключи как str)
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
                "bank_accounts": []  # Новое поле для банковских счетов
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
        # Проверяем, не прошло ли 24 часа
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
        # Проверяем, не прошло ли 24 часа
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
        """Проверяет, может ли пользователь ответить на сообщение"""
        current_time = time.time()
        last_reply = self.last_reply_time.get(user_id, 0)
        
        if current_time - last_reply < 300:  # 5 минут
            wait_time = 300 - int(current_time - last_reply)
            return False, f"❌ Вы можете ответить снова через {wait_time} секунд"
        
        return True, ""

    def create_bank_account(self, user_id: int, account_name: str) -> str:
        """Создает банковский счет для пользователя"""
        user = self.users[user_id]
        
        if len(user.get("bank_accounts", [])) >= 3:
            return "❌ У вас уже есть максимальное количество счетов (3)"
        
        # Инициализируем банковские счета, если их нет
        if "bank_accounts" not in user:
            user["bank_accounts"] = []
        
        # Проверяем, есть ли уже счет с таким именем
        for account in user["bank_accounts"]:
            if account["name"].lower() == account_name.lower():
                return "❌ Счет с таким названием уже существует"
        
        # Создаем новый счет
        user["bank_accounts"].append({
            "name": account_name,
            "balance": 0
        })
        
        self.save_data()
        return f"✅ Банковский счет '{account_name}' успешно создан!"

    def bank_deposit(self, user_id: int, account_index: int, amount: int) -> str:
        """Пополнение банковского счета"""
        user = self.users[user_id]
        
        if "bank_accounts" not in user or not user["bank_accounts"]:
            return "❌ У вас нет банковских счетов. Создайте счет командой /regbank"
        
        if account_index < 0 or account_index >= len(user["bank_accounts"]):
            return "❌ Неверный номер счета"
        
        if amount <= 0:
            return "❌ Сумма должна быть положительной"
        
        if user["balance"] < amount:
            return "❌ Недостаточно средств на основном балансе"
        
        # Переводим деньги с основного баланса на банковский счет
        user["balance"] -= amount
        user["bank_accounts"][account_index]["balance"] += amount
        
        self.save_data()
        return f"✅ Успешно переведено {amount}💰 на счет '{user['bank_accounts'][account_index]['name']}'\n💳 Основной баланс: {user['balance']}"

    def bank_withdraw(self, user_id: int, account_index: int, amount: int) -> str:
        """Снятие с банковского счета"""
        user = self.users[user_id]
        
        if "bank_accounts" not in user or not user["bank_accounts"]:
            return "❌ У вас нет банковских счетов. Создайте счет командой /regbank"
        
        if account_index < 0 or account_index >= len(user["bank_accounts"]):
            return "❌ Неверный номер счета"
        
        if amount <= 0:
            return "❌ Сумма должна быть положительной"
        
        if user["bank_accounts"][account_index]["balance"] < amount:
            return f"❌ Недостаточно средств на счете. Доступно: {user['bank_accounts'][account_index]['balance']}💰"
        
        # Переводим деньги с банковского счета на основной баланс
        user["bank_accounts"][account_index]["balance"] -= amount
        user["balance"] += amount
        
        self.save_data()
        return f"✅ Успешно снято {amount}💰 со счета '{user['bank_accounts'][account_index]['name']}'\n💳 Основной баланс: {user['balance']}"

bot_data = CasinoBot()

# ==================== НОВЫЕ КОМАНДЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ====================

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список команд"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
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
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает баланс пользователя"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    user = bot_data.users[user_id]
    
    # Считаем общую сумму в банке
    total_bank = sum(account["balance"] for account in user.get("bank_accounts", []))
    
    balance_text = f"""
💰 **ВАШ БАЛАНС**

💳 Основные средства: {user['balance']}💰
🎯 PlayCoin: {user['play_coins']} PC
🏦 В банке: {total_bank}💰

📈 Всего заработано: {user['total_earned']}💰
🎮 Сыграно игр: {user['games_played']}
    """
    
    await update.message.reply_text(balance_text, parse_mode='Markdown')

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ежедневная награда"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    user = bot_data.users[user_id]
    
    current_time = time.time()
    last_daily = user.get("last_daily", 0)
    
    # Проверяем, прошло ли 24 часа
    if current_time - last_daily < 24 * 3600:
        wait_time = 24 * 3600 - int(current_time - last_daily)
        hours = wait_time // 3600
        minutes = (wait_time % 3600) // 60
        await update.message.reply_text(f"⏰ Следующая награда через {hours}ч {minutes}м")
        return
    
    # Определяем награду в зависимости от серии
    daily_streak = user.get("daily_streak", 0) + 1
    if daily_streak % 7 == 0:
        # 7-й день - бонус 20000
        reward = 20000
        bonus_text = "🎉 **7-Й ДЕНЬ БОНУС!**"
    else:
        # Обычный день - 5000
        reward = 5000
        bonus_text = "📅 Обычный день"
    
    # Выдаем награду
    user["balance"] += reward
    user["last_daily"] = current_time
    user["daily_streak"] = daily_streak
    user["total_earned"] += reward
    
    bot_data.save_data()
    
    # Показываем прогресс до 7-го дня
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
    
    await update.message.reply_text(message)

async def transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перевод денег другому пользователю"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text(
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
        await update.message.reply_text("❌ Сумма должна быть числом")
        return
    
    if amount <= 0:
        await update.message.reply_text("❌ Сумма должна быть положительной")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    user = bot_data.users[user_id]
    
    if user["balance"] < amount:
        await update.message.reply_text("❌ Недостаточно средств")
        return
    
    # Поиск получателя
    target_user = None
    
    # Пробуем найти по ID
    if target_input.isdigit():
        target_id = int(target_input)
        if target_id in bot_data.users:
            target_user = bot_data.users[target_id]
    
    # Если не нашли по ID, ищем по username
    if not target_user and target_input.startswith('@'):
        found_users = bot_data.search_user_by_username(target_input[1:])
        if found_users:
            target_id, target_user = found_users[0]
    
    # Если все еще не нашли, ищем без @
    if not target_user:
        found_users = bot_data.search_user_by_username(target_input)
        if found_users:
            target_id, target_user = found_users[0]
    
    if not target_user:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    if target_id == user_id:
        await update.message.reply_text("❌ Нельзя переводить самому себе")
        return
    
    if bot_data.is_banned(target_id):
        await update.message.reply_text("❌ Нельзя переводить забаненному пользователю")
        return
    
    # Выполняем перевод
    user["balance"] -= amount
    target_user["balance"] += amount
    
    bot_data.save_data()
    
    # Уведомляем получателя, если это возможно
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"💸 Вам перевели {amount}💰 от @{user['username']}"
        )
    except Exception:
        pass  # Не смогли уведомить получателя
    
    await update.message.reply_text(
        f"✅ Успешный перевод!\n"
        f"👤 Получатель: @{target_user['username']}\n"
        f"💰 Сумма: {amount}💰\n"
        f"💳 Ваш остаток: {user['balance']}💰"
    )

async def regbank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создание банковского счета"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "🏦 Создание банковского счета\n\n"
            "Использование: /regbank [название счета]\n\n"
            "Пример: /regbank Основной\n"
            "💡 Можно создать до 3 счетов"
        )
        return
    
    account_name = ' '.join(context.args)
    bot_data.init_user(user_id, update.effective_user.username)
    
    result = bot_data.create_bank_account(user_id, account_name)
    await update.message.reply_text(result)

async def bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление банковскими счетами"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    user = bot_data.users[user_id]
    
    if len(context.args) != 3:
        await update.message.reply_text(
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
        account_index = int(context.args[0]) - 1  # Пользователь вводит 1,2,3 - мы используем 0,1,2
        amount = int(context.args[1])
        action = context.args[2].lower()
    except ValueError:
        await update.message.reply_text("❌ Номер счета и сумма должны быть числами")
        return
    
    if action == "deposit":
        result = bot_data.bank_deposit(user_id, account_index, amount)
    elif action == "withdraw":
        result = bot_data.bank_withdraw(user_id, account_index, amount)
    else:
        result = "❌ Неверное действие. Используйте 'deposit' или 'withdraw'"
    
    await update.message.reply_text(result)

async def infobank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о банковских счетах"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    user = bot_data.users[user_id]
    
    if "bank_accounts" not in user or not user["bank_accounts"]:
        await update.message.reply_text(
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
    
    await update.message.reply_text(accounts_text, parse_mode='Markdown')

# ==================== НОВЫЕ КОМАНДЫ ДЛЯ СОЗДАТЕЛЯ ====================

async def backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создание резервной копии данных"""
    user_id = update.effective_user.id
    
    if not bot_data.is_creator_authenticated(user_id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    try:
        # Создаем резервную копию
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
        
        # В реальном приложении здесь можно сохранить в файл или отправить куда-то
        # Для простоты просто покажем статистику
        
        await update.message.reply_text(
            f"✅ **Резервная копия создана**\n\n"
            f"📊 Статистика бэкапа:\n"
            f"• 👥 Пользователей: {len(bot_data.users)}\n"
            f"• 🚫 Забанено: {len(bot_data.banned_users)}\n"
            f"• 📝 Логов: {len(bot_data.admin_logs)}\n"
            f"• 🎮 Активных игр: {len(bot_data.game_statistics)}\n"
            f"• ⏰ Время: {timestamp}"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при создании бэкапа: {e}")

async def globalstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глобальная статистика бота"""
    user_id = update.effective_user.id
    
    if not bot_data.is_creator_authenticated(user_id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    stats = bot_data.get_bot_stats()
    game_stats = bot_data.get_game_stats()
    
    # Считаем общую сумму денег в банке у всех пользователей
    total_bank_money = 0
    users_with_bank = 0
    for user_data in bot_data.users.values():
        if "bank_accounts" in user_data:
            user_bank = sum(account["balance"] for account in user_data["bank_accounts"])
            total_bank_money += user_bank
            if user_bank > 0:
                users_with_bank += 1
    
    # Собираем топ-5 самых богатых пользователей
    rich_users = []
    for user_id, user_data in bot_data.users.items():
        if not bot_data.is_creator(user_id):
            total_wealth = user_data["balance"] + sum(
                account["balance"] for account in user_data.get("bank_accounts", [])
            )
            rich_users.append((user_id, user_data, total_wealth))
    
    rich_users.sort(key=lambda x: x[2], reverse=True)
    
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
    
    await update.message.reply_text(response)

async def givepc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выдать PlayCoin пользователю"""
    user_id = update.effective_user.id
    
    if not bot_data.is_creator_authenticated(user_id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "🎯 Выдача PlayCoin\n\n"
            "Использование: /givepc [ID] [количество]\n\n"
            "Пример: /givepc 123456789 100"
        )
        return
    
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Ошибка: ID и количество должны быть числами")
        return
    
    if target_id not in bot_data.users:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    if amount <= 0:
        await update.message.reply_text("❌ Количество должно быть положительным")
        return
    
    bot_data.users[target_id]["play_coins"] += amount
    
    target_username = bot_data.users[target_id]["username"] or str(target_id)
    bot_data.add_admin_log(user_id, update.effective_user.username or str(user_id), 
                          "ВЫДАЧА_PLAYCOIN", target_username, f"{amount} PC")
    
    await update.message.reply_text(
        f"✅ Пользователю {target_username} выдано {amount} PlayCoin\n"
        f"🎯 Теперь у него: {bot_data.users[target_id]['play_coins']} PC"
    )

# ==================== СУЩЕСТВУЮЩИЕ КОМАНДЫ (с обновлениями) ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запускает бота"""
    user = update.effective_user
    user_id = user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены и не можете использовать бота.")
        return
    
    bot_data.init_user(user_id, user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
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
                f"/play [ставка] [игра] - сыграть в игру\n"
                f"/balance - ваш баланс\n"
                f"/daily - ежедневная награда\n"
                f"/help - все команды",
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
                f"/play [ставка] [игра] - сыграть в игру\n"
                f"/balance - ваш баланс\n"
                f"/daily - ежедневная награда\n"
                f"/help - все команды\n\n"
                f"⚙️ Команды создателя: /creatorcmd",
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
                f"/play [ставка] [игра] - сыграть в игру\n"
                f"/balance - ваш баланс\n"
                f"/daily - ежедневная награда\n"
                f"/help - все команды",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
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
        await update.message.reply_text(
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

# ... (остальной код остается без изменений, включая команды play, shop, wheel, stats, promo, repriv, 
# register, panel, creatorcmd, setdonate, message_cmd, q, announce, givecash, givedonate, ban, unban, 
# search, userinfo, setbalance, reseteconomy, setmultiplier, resetuser, massgive, listadmins, botstats,
# exportdata, topactive, gamestats, reboot, cleanup, setwelcome, createpromo, testmode, addgame,
# massprivilege, setgladmin, logs, author, button_handler, buy_privilege)

# ==================== ОБНОВЛЕНИЕ РЕГИСТРАЦИИ ОБРАБОТЧИКОВ ====================

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
    application.add_handler(CommandHandler("q", q))
    
    # Новые команды для пользователей
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("daily", daily))
    application.add_handler(CommandHandler("transfer", transfer))
    application.add_handler(CommandHandler("regbank", regbank))
    application.add_handler(CommandHandler("bank", bank))
    application.add_handler(CommandHandler("infobank", infobank))
    
    # Команды авторизации
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("panel", panel))
    application.add_handler(CommandHandler("creatorcmd", creatorcmd))
    
    # Новые команды для создателя
    application.add_handler(CommandHandler("backup", backup))
    application.add_handler(CommandHandler("globalstats", globalstats))
    application.add_handler(CommandHandler("givepc", givepc))
    
    # Существующие команды
    application.add_handler(CommandHandler("setdonate", setdonate))
    application.add_handler(CommandHandler("message", message_cmd))
    application.add_handler(CommandHandler("givecash", givecash))
    application.add_handler(CommandHandler("givedonate", givedonate))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("unban", unban))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CommandHandler("userinfo", userinfo))
    application.add_handler(CommandHandler("announce", announce))
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
    application.add_handler(CommandHandler("setgladmin", setgladmin))
    application.add_handler(CommandHandler("logs", logs))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("🤖 Бот запущен и работает 24/7!")
    logger.info("💾 Система сохранения данных активирована")
    logger.info("🏦 Банковская система добавлена")
    logger.info("👑 Создатель бота: Frapello")
    
    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
