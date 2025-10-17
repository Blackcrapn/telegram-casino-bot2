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
            4: {"plays": 0, "total_bets": 0, "total_wins": 0}  # Новая игра Удача
        }
        
        self.games = {
            1: {"name": "🎡 Рулетка", "description": "Угадай число от 1 до 36"},
            2: {"name": "🎯 Координаты", "description": "Угадай координаты на плоскости"},
            3: {"name": "🪙 Монетка", "description": "Орёл или решка"},
            4: {"name": "🍀 Удача", "description": "50/50 шанс выиграть x2"}  # Новая игра
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
                "last_activity": time.time()
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

bot_data = CasinoBot()

# ==================== ОБНОВЛЕННАЯ КОМАНДА AUTHOR ====================

async def author(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация об авторе"""
    await update.message.reply_text("👨‍💻 Автор бота: Frapello")

# ==================== ОБНОВЛЕННАЯ КОМАНДА PLAY (С ДОБАВЛЕНИЕМ НОВОЙ ИГРЫ) ====================

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сыграть в игру [ставка] [номер игры: Рулетка - 1, Координаты - 2, Монетка - 3, Удача - 4]"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
    if len(context.args) != 2:
        await update.message.reply_text(
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
        await update.message.reply_text("❌ Ошибка: ставка и номер игры должны быть числами")
        return

    if game_id not in bot_data.games:
        await update.message.reply_text("❌ Ошибка: игра не найдена")
        return

    user = bot_data.users[user_id]
    is_creator = bot_data.is_creator(user_id)
    
    if not is_creator and bet > user["balance"]:
        await update.message.reply_text("❌ Недостаточно средств")
        return

    if bet <= 0:
        await update.message.reply_text("❌ Ставка должна быть положительной")
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

    elif game_id == 4:  # Новая игра Удача
        # Шанс 50/50
        if random.choice([True, False]):
            win_amount = bet * 2  # Выигрыш x2
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
    await update.message.reply_text(result_text)

# ==================== ОСТАЛЬНЫЕ КОМАНДЫ (без изменений) ====================

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
                f"/play [ставка] [игра] - сыграть в игру\n"
                f"/shop - магазин привилегий\n"
                f"/leaderboard - таблица лидеров\n"
                f"/stats - ваша статистика\n"
                f"/wheel - колесо удачи (100 PC)\n"
                f"/author - информация об авторе\n"
                f"/promo [код] - активировать промокод\n"
                f"/repriv [привилегия] - сменить привилегию\n\n"
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
                f"/play [ставка] [игра] - сыграть в игру\n"
                f"/shop - магазин привилегий\n"
                f"/leaderboard - таблица лидеров\n"
                f"/stats - ваша статистика\n"
                f"/wheel - колесо удачи (100 PC)\n"
                f"/author - информация об авторе\n"
                f"/promo [код] - активировать промокод\n"
                f"/repriv [привилегия] - сменить привилегию\n\n"
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
            f"📋 Доступные команды:\n"
            f"/play [ставка] [игра] - сыграть в игру\n"
            f"/shop - магазин привилегий\n"
            f"/leaderboard - таблица лидеров\n"
            f"/stats - ваша статистика\n"
            f"/wheel - колесо удачи (100 PC)\n"
            f"/author - информация об авторе\n"
            f"/promo [код] - активировать промокод\n"
            f"/repriv [привилегия] - сменить привилегию\n"
            f"/q [сообщение] - ответить администрации",
            parse_mode='Markdown'
        )

async def wheel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Прокрутить колесо удачи (стоимость: 100 PlayCoin)"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
    result = bot_data.spin_wheel(user_id)
    user = bot_data.users[user_id]
    
    result_text = f"{result}\n\n🎯 Осталось PlayCoin: {'∞' if bot_data.is_creator(user_id) else user['play_coins']}"
    await update.message.reply_text(result_text)

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Магазин привилегий"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
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
    
    await update.message.reply_text(
        f"🏪 Магазин привилегий\n\n"
        f"💰 Баланс: {'∞' if bot_data.is_creator(user_id) else user['balance']}\n"
        f"🎯 PlayCoin: {'∞' if bot_data.is_creator(user_id) else user['play_coins']}\n"
        f"👑 Привилегия: {bot_data.privileges[user['privilege']]['title'] if user['privilege'] else 'Нет'}",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if bot_data.is_banned(user_id):
        await query.edit_message_text("❌ Вы забанены.")
        return
    
    data = query.data
    
    if data.startswith("buy_"):
        priv_id = data[4:]
        await buy_privilege(user_id, priv_id, query)

async def buy_privilege(user_id: int, priv_id: str, query):
    if priv_id not in bot_data.privileges:
        await query.edit_message_text("❌ Ошибка: привилегия не найдена")
        return
    
    user = bot_data.users[user_id]
    priv_info = bot_data.privileges[priv_id]
    
    if not bot_data.is_creator(user_id) and user["balance"] < priv_info["cost"]:
        await query.edit_message_text("❌ Недостаточно средств")
        return
    
    if not bot_data.is_creator(user_id):
        user["balance"] -= priv_info["cost"]
    
    user["privilege"] = priv_id
    
    bot_data.save_data()
    await query.edit_message_text(
        f"🎉 Поздравляем с покупкой!\n"
        f"Теперь у вас: {priv_info['title']}\n"
        f"Бонус: +{int((priv_info['bonus'] - 1) * 100)}% к выигрышам\n\n"
        f"💰 Остаток: {'∞' if bot_data.is_creator(user_id) else user['balance']}"
    )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает таблицу лидеров"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return
    
    leaderboard_data = bot_data.get_leaderboard()
    
    if not leaderboard_data:
        await update.message.reply_text("📊 Пока нет данных для таблицы лидеров")
        return
    
    text = "🏆 ТОП-10 ИГРОКОВ 🏆\n\n"
    
    for i, (user_id, user_data) in enumerate(leaderboard_data, 1):
        username = f"@{user_data['username']}" if user_data["username"] else f"ID: {user_id}"
        privilege_title = ""
        if user_data["privilege"]:
            privilege_title = bot_data.privileges[user_data["privilege"]]["title"]
        
        text += f"{i}. {username} {privilege_title}\n"
        text += f"   💰 Заработано: {user_data['total_earned']}\n\n"
    
    await update.message.reply_text(text)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает вашу статистику"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
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
    
    await update.message.reply_text(
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

async def promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Активировать промокод [код]"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
    if not context.args:
        await update.message.reply_text("Использование: /promo [код]")
        return
    
    code = context.args[0]
    result = bot_data.activate_promo_code(user_id, code)
    await update.message.reply_text(result, parse_mode='Markdown')

async def repriv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сменить привилегию [название привилегии]"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
    if not context.args:
        await update.message.reply_text(
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
    await update.message.reply_text(result)

# ==================== КОМАНДЫ АВТОРИЗАЦИИ ====================

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Авторизация создателя [пароль]"""
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
        bot_data.users[user_id]["creator_auth_time"] = time.time()
        bot_data.save_data()
        await update.message.reply_text(
            "✅ Авторизация успешна! Теперь вам доступны все команды создателя.\n\n"
            "💡 Авторизация действует 24 часа\n"
            "📋 Используйте /creatorcmd для просмотра команд"
        )
    else:
        await update.message.reply_text("❌ Неверный пароль")

async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Авторизация администратора [пароль]"""
    user_id = update.effective_user.id
    
    if not bot_data.is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администраторам")
        return
    
    if bot_data.is_admin_authenticated(user_id):
        await update.message.reply_text("✅ Вы уже авторизованы как администратор")
        return
    
    if user_id not in bot_data.admin_passwords:
        if not context.args:
            await update.message.reply_text("🔐 Создайте пароль для авторизации. Пример: /panel 123892hdi8738")
            return
        
        password = context.args[0]
        bot_data.admin_passwords[user_id] = password
        bot_data.save_data()
        await update.message.reply_text(
            f"✅ Пароль установлен! Теперь авторизуйтесь: /panel {password}\n\n"
            f"💡 Авторизация действует 24 часа"
        )
        return
    
    if not context.args:
        await update.message.reply_text("🔐 Авторизуйтесь: /panel [ваш пароль]")
        return
    
    password = context.args[0]
    
    if user_id in bot_data.admin_passwords and bot_data.admin_passwords[user_id] == password:
        bot_data.users[user_id]["admin_authenticated"] = True
        bot_data.users[user_id]["admin_auth_time"] = time.time()
        bot_data.save_data()
        await update.message.reply_text(
            "✅ Авторизация успешна! Теперь вам доступны команды администратора.\n\n"
            "💡 Авторизация действует 24 часа"
        )
    else:
        await update.message.reply_text("❌ Неверный пароль")

# ==================== НОВЫЕ КОМАНДЫ ====================

async def setdonate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выдает эксклюзивные донаты [ID пользователя] [название доната]"""
    user_id = update.effective_user.id
    
    if not bot_data.is_admin_authenticated(user_id):
        await update.message.reply_text("❌ Авторизуйтесь как администратор: /panel [пароль]")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text(
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
        await update.message.reply_text("❌ Ошибка: ID должен быть числом")
        return
    
    if target_id not in bot_data.users:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    if donate_name not in bot_data.exclusive_donates:
        await update.message.reply_text("❌ Неверное название доната. Доступные: TITAN, FLE, DRAGON")
        return
    
    bot_data.users[target_id]["exclusive_donate"] = donate_name
    donate_desc = bot_data.exclusive_donates[donate_name]["description"]
    
    # Логирование для администраторов (не создателей)
    if not bot_data.is_creator(user_id):
        admin_username = update.effective_user.username or str(user_id)
        target_username = bot_data.users[target_id]["username"] or str(target_id)
        bot_data.add_admin_log(user_id, admin_username, "ВЫДАЧА_ДОНАТА", target_username, donate_name)
    
    await update.message.reply_text(
        f"✅ Пользователю {target_id} выдан донат {donate_name}\n"
        f"📝 {donate_desc}"
    )

async def message_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить сообщение пользователю [ID пользователя] [сообщение]"""
    user_id = update.effective_user.id
    
    if not bot_data.is_admin_authenticated(user_id):
        await update.message.reply_text("❌ Авторизуйтесь как администратор: /panel [пароль]")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "📨 Отправка сообщения пользователю\n\n"
            "Использование: /message [ID пользователя] [текст сообщения]\n\n"
            "Пример: /message 123456789 Привет! Как дела?"
        )
        return
    
    try:
        target_id = int(context.args[0])
        message_text = ' '.join(context.args[1:])
    except ValueError:
        await update.message.reply_text("❌ Ошибка: ID должен быть числом")
        return
    
    if target_id not in bot_data.users:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    try:
        sender_role = "Создателя" if bot_data.is_creator(user_id) else "Администратора"
        await context.bot.send_message(
            chat_id=target_id,
            text=f"📨 Сообщение от {sender_role}:\n\n{message_text}"
        )
        await update.message.reply_text(f"✅ Сообщение отправлено пользователю {target_id}")
    except Exception as e:
        await update.message.reply_text(f"❌ Не удалось отправить сообщение: {e}")

async def creatorcmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает все команды создателя"""
    user_id = update.effective_user.id
    
    if not bot_data.is_creator(user_id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
        return
    
    if not bot_data.is_creator_authenticated(user_id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
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
        "/setdonate [ID] [донат] - выдать эксклюзивный донат"
    ]
    
    await update.message.reply_text("\n".join(commands_list))

async def q(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ответить создателю/администратору [сообщение]"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "💬 Ответить создателю/администратору\n\n"
            "Использование: /q [текст сообщения]\n\n"
            "⚠️ Можно использовать 1 раз каждые 5 минут"
        )
        return
    
    # Проверяем возможность ответа
    can_reply, message = bot_data.can_user_reply(user_id)
    if not can_reply:
        await update.message.reply_text(message)
        return
    
    message_text = ' '.join(context.args)
    user_data = bot_data.users.get(user_id, {})
    username = user_data.get("username", "Неизвестно")
    
    # Обновляем время последнего ответа
    bot_data.last_reply_time[user_id] = time.time()
    bot_data.save_data()
    
    # Отправляем сообщение всем администраторам и создателю
    sent_count = 0
    for admin_id, admin_data in bot_data.users.items():
        if bot_data.is_admin(admin_id):
            try:
                await context.bot.send_message(
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
        await update.message.reply_text("✅ Ваше сообщение отправлено!")
    else:
        await update.message.reply_text("❌ В данный момент нет активных администраторов")

# ==================== ОБНОВЛЕННАЯ КОМАНДА ANNOUNCE ====================

async def announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глобальная рассылка [текст]"""
    user_id = update.effective_user.id
    
    if not bot_data.is_admin_authenticated(user_id):
        await update.message.reply_text("❌ Авторизуйтесь как администратор: /panel [пароль]")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📢 Глобальная рассылка сообщения\n\n"
            "Использование: /announce [текст сообщения]\n\n"
            "💡 Пользователи смогут ответить командой /q"
        )
        return
    
    message = ' '.join(context.args)
    sender_role = "Создателя" if bot_data.is_creator(user_id) else "Администратора"
    
    sent_count = 0
    failed_count = 0
    
    users_to_notify = list(bot_data.users.items())[:100]  # Ограничение для безопасности
    
    for target_id, user_data in users_to_notify:
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"📢 Сообщение от {sender_role}:\n\n{message}\n\n"
                     f"💬 Ответить: /q [ваше сообщение]"
            )
            sent_count += 1
            time.sleep(0.1)  # Защита от лимитов Telegram
        except Exception as e:
            failed_count += 1
            logging.error(f"Не удалось отправить сообщение пользователю {target_id}: {e}")
    
    await update.message.reply_text(
        f"✅ Рассылка завершена:\n"
        f"• Отправлено: {sent_count}\n"
        f"• Не удалось: {failed_count}\n"
        f"• Всего пользователей в базе: {len(bot_data.users)}"
    )

# ==================== КОМАНДЫ АДМИНИСТРАТОРА ====================

async def givecash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выдать монеты пользователю [ID] [количество]"""
    user_id = update.effective_user.id
    
    if not bot_data.is_admin_authenticated(user_id):
        await update.message.reply_text("❌ Авторизуйтесь как администратор: /panel [пароль]")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("Использование: /givecash [id] [amount]")
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
    
    bot_data.users[target_id]["balance"] += amount
    
    if not bot_data.is_creator(user_id):
        admin_username = update.effective_user.username or str(user_id)
        target_username = bot_data.users[target_id]["username"] or str(target_id)
        bot_data.add_admin_log(user_id, admin_username, "ВЫДАЧА_МОНЕТ", target_username, f"{amount} монет")
    
    await update.message.reply_text(f"✅ Баланс пользователя {target_id} пополнен на {amount}")

async def givedonate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выдать донат пользователю [ID] [название доната]"""
    user_id = update.effective_user.id
    
    if not bot_data.is_admin_authenticated(user_id):
        await update.message.reply_text("❌ Авторизуйтесь как администратор: /panel [пароль]")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("Использование: /givedonate [id] [donate]\nДоступные донаты: TITAN, FLE, DRAGON")
        return
    
    try:
        target_id = int(context.args[0])
        donate_name = context.args[1].upper()
    except ValueError:
        await update.message.reply_text("❌ Ошибка: ID должен быть числом")
        return
    
    if target_id not in bot_data.users:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    if donate_name not in bot_data.exclusive_donates:
        await update.message.reply_text("❌ Неверное название доната. Доступные: TITAN, FLE, DRAGON")
        return
    
    bot_data.users[target_id]["exclusive_donate"] = donate_name
    donate_desc = bot_data.exclusive_donates[donate_name]["description"]
    
    if not bot_data.is_creator(user_id):
        admin_username = update.effective_user.username or str(user_id)
        target_username = bot_data.users[target_id]["username"] or str(target_id)
        bot_data.add_admin_log(user_id, admin_username, "ВЫДАЧА_ДОНАТА", target_username, donate_name)
    
    await update.message.reply_text(f"✅ Пользователю {target_id} выдан донат {donate_name}\n{donate_desc}")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Забанить пользователя [ID]"""
    user_id = update.effective_user.id
    
    if not bot_data.is_admin_authenticated(user_id):
        await update.message.reply_text("❌ Авторизуйтесь как администратор: /panel [пароль]")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Использование: /ban [id]")
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Ошибка: ID должен быть числом")
        return
    
    if bot_data.is_creator(target_id):
        await update.message.reply_text("❌ Нельзя забанить создателя")
        return
    
    bot_data.banned_users.add(target_id)
    
    if not bot_data.is_creator(user_id):
        admin_username = update.effective_user.username or str(user_id)
        target_username = bot_data.users[target_id]["username"] if target_id in bot_data.users else str(target_id)
        bot_data.add_admin_log(user_id, admin_username, "БАН", target_username)
    
    await update.message.reply_text(f"✅ Пользователь {target_id} забанен")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Разбанить пользователя [ID]"""
    user_id = update.effective_user.id
    
    if not bot_data.is_admin_authenticated(user_id):
        await update.message.reply_text("❌ Авторизуйтесь как администратор: /panel [пароль]")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Использование: /unban [id]")
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Ошибка: ID должен быть числом")
        return
    
    if target_id in bot_data.banned_users:
        bot_data.banned_users.remove(target_id)
        
        if not bot_data.is_creator(user_id):
            admin_username = update.effective_user.username or str(user_id)
            target_username = bot_data.users[target_id]["username"] if target_id in bot_data.users else str(target_id)
            bot_data.add_admin_log(user_id, admin_username, "РАЗБАН", target_username)
        
        await update.message.reply_text(f"✅ Пользователь {target_id} разбанен")
    else:
        await update.message.reply_text("❌ Пользователь не забанен")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Найти пользователя по username [@username]"""
    user_id = update.effective_user.id
    
    if not bot_data.is_admin_authenticated(user_id):
        await update.message.reply_text("❌ Авторизуйтесь как администратор: /panel [пароль]")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Использование: /search [@username]\nПример: /search @username")
        return
    
    username = context.args[0]
    found_users = bot_data.search_user_by_username(username)
    
    if not found_users:
        await update.message.reply_text(f"❌ Пользователь {username} не найден")
        return
    
    response = f"🔍 Найденные пользователи по запросу {username}:\n\n"
    for user_id, user_data in found_users:
        response += f"👤 Username: @{user_data['username']}\n"
        response += f"🆔 ID: `{user_id}`\n"
        response += f"💰 Баланс: {user_data['balance']}\n"
        response += f"🎮 Игр сыграно: {user_data['games_played']}\n"
        response += f"🏆 Заработано: {user_data['total_earned']}\n"
        response += "─" * 30 + "\n"
    
    await update.message.reply_text(response, parse_mode='Markdown')

async def userinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о пользователе [ID]"""
    user_id = update.effective_user.id
    
    if not bot_data.is_admin_authenticated(user_id):
        await update.message.reply_text("❌ Авторизуйтесь как администратор: /panel [пароль]")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Использование: /userinfo [id]")
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Ошибка: ID должен быть числом")
        return
    
    if target_id not in bot_data.users:
        await update.message.reply_text("❌ Пользователь не найден")
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
    
    await update.message.reply_text(response)

# ==================== КОМАНДЫ СОЗДАТЕЛЯ ====================

async def setbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить баланс пользователю [ID] [сумма]"""
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("Использование: /setbalance [id] [amount]")
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
    
    bot_data.users[target_id]["balance"] = amount
    bot_data.save_data()
    await update.message.reply_text(f"✅ Баланс пользователя {target_id} установлен в {amount}")

async def reseteconomy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Полный сброс экономики"""
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    bot_data.reset_economy()
    await update.message.reply_text("✅ Экономика бота полностью сброшена!")

async def setmultiplier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить глобальный множитель [значение]"""
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Использование: /setmultiplier [value]")
        return
    
    try:
        multiplier = float(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Ошибка: множитель должен быть числом")
        return
    
    bot_data.global_multiplier = multiplier
    bot_data.save_data()
    await update.message.reply_text(f"✅ Глобальный множитель установлен: {multiplier}x")

async def resetuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбросить статистику пользователя [ID]"""
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Использование: /resetuser [id]")
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Ошибка: ID должен быть числом")
        return
    
    if target_id not in bot_data.users:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    if bot_data.is_creator(target_id):
        await update.message.reply_text("❌ Нельзя сбросить статистику создателя")
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
    await update.message.reply_text(f"✅ Статистика пользователя {target_id} сброшена")

async def massgive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Массовая выдача монет [сумма] [критерий]"""
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /massgive [amount] [criteria]\nКритерии: all, with_privilege, no_privilege")
        return
    
    try:
        amount = int(context.args[0])
        criteria = context.args[1].lower()
    except ValueError:
        await update.message.reply_text("❌ Ошибка: количество должно быть числом")
        return
    
    if criteria not in ["all", "with_privilege", "no_privilege"]:
        await update.message.reply_text("❌ Неверный критерий. Доступно: all, with_privilege, no_privilege")
        return
    
    affected = bot_data.mass_give_coins(amount, criteria)
    await update.message.reply_text(f"✅ Выдано {amount} монет {affected} пользователям (критерий: {criteria})")

async def listadmins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список администраторов"""
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    admins = []
    for user_id, user_data in bot_data.users.items():
        if user_data.get("is_admin", False) or bot_data.is_creator(user_id):
            admins.append((user_id, user_data))
    
    if not admins:
        await update.message.reply_text("📋 Администраторы не найдены")
        return
    
    response = "👑 АДМИНИСТРАТОРЫ БОТА:\n\n"
    for user_id, user_data in admins:
        role = "👑 СОЗДАТЕЛЬ" if bot_data.is_creator(user_id) else "🔧 АДМИНИСТРАТОР"
        response += f"{role}\n"
        response += f"👤 @{user_data['username']}\n"
        response += f"🆔 ID: {user_id}\n"
        response += f"🎮 Игр: {user_data['games_played']}\n"
        response += "─" * 30 + "\n"
    
    await update.message.reply_text(response)

async def botstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика бота"""
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
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
    
    await update.message.reply_text(response)

async def exportdata(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспорт данных пользователей"""
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if not bot_data.users:
        await update.message.reply_text("❌ Нет данных для экспорта")
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
    await update.message.reply_text(response)

async def topactive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Топ активных игроков [лимит]"""
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    limit = 10
    if context.args and context.args[0].isdigit():
        limit = min(int(context.args[0]), 20)
    
    top_users = bot_data.get_top_active_users(limit)
    
    if not top_users:
        await update.message.reply_text("❌ Нет данных о пользователях")
        return
    
    response = f"🏆 ТОП-{limit} АКТИВНЫХ ИГРОКОВ:\n\n"
    for i, (user_id, user_data) in enumerate(top_users, 1):
        response += f"{i}. @{user_data['username']}\n"
        response += f"   🎮 Игр: {user_data['games_played']}\n"
        response += f"   💰 Баланс: {user_data['balance']}\n"
        response += "─" * 30 + "\n"
    
    await update.message.reply_text(response)

async def gamestats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Детальная статистика игр"""
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
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
    
    await update.message.reply_text(response)

async def reboot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перезагрузка бота"""
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    await update.message.reply_text("🔄 Перезагрузка бота...")
    await update.message.reply_text("✅ Бот 'перезагружен'. Все данные сохранены.")

async def cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить неактивных пользователей [дни]"""
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    days = 30
    if context.args and context.args[0].isdigit():
        days = int(context.args[0])
    
    removed_count = bot_data.cleanup_inactive_users(days)
    await update.message.reply_text(f"🧹 Удалено {removed_count} неактивных пользователей (неактивность > {days} дней)")

async def setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить приветственное сообщение [текст]"""
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /setwelcome [текст приветствия]")
        return
    
    welcome_text = ' '.join(context.args)
    bot_data.welcome_message = welcome_text
    bot_data.save_data()
    await update.message.reply_text(f"✅ Приветственное сообщение установлено:\n\n{welcome_text}")

async def createpromo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создать промокод [код] [тип_награды] [значение]"""
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

async def testmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Включить/выключить тестовый режим [on/off]"""
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if not context.args:
        await update.message.reply_text(f"🎯 Тестовый режим: {'ВКЛ' if bot_data.test_mode else 'ВЫКЛ'}")
        return
    
    mode = context.args[0].lower()
    if mode in ["on", "вкл", "true", "1"]:
        bot_data.test_mode = True
        bot_data.save_data()
        await update.message.reply_text("✅ Тестовый режим ВКЛЮЧЕН")
    elif mode in ["off", "выкл", "false", "0"]:
        bot_data.test_mode = False
        bot_data.save_data()
        await update.message.reply_text("✅ Тестовый режим ВЫКЛЮЧЕН")
    else:
        await update.message.reply_text("❌ Использование: /testmode [on/off]")

async def addgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить новую игру [название] [описание]"""
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /addgame [название] [описание]")
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
    await update.message.reply_text(f"✅ Новая игра добавлена:\nID: {new_game_id}\nНазвание: {game_name}\nОписание: {game_description}")

async def massprivilege(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Массовая выдача привилегии [привилегия]"""
    if not bot_data.is_creator_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Использование: /massprivilege [привилегия]\nДоступно: bronze, silver, gold, platinum")
        return
    
    privilege = context.args[0].lower()
    if privilege not in bot_data.privileges:
        await update.message.reply_text("❌ Неверная привилегия. Доступно: bronze, silver, gold, platinum")
        return
    
    affected = 0
    for user_id, user_data in bot_data.users.items():
        if not bot_data.is_creator(user_id):
            user_data["privilege"] = privilege
            affected += 1
    
    privilege_title = bot_data.privileges[privilege]["title"]
    bot_data.save_data()
    await update.message.reply_text(f"✅ Привилегия {privilege_title} выдана {affected} пользователям")

async def setgladmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Назначить главного администратора [@username]"""
    user_id = update.effective_user.id
    
    if not bot_data.is_creator_authenticated(user_id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Использование: /setgladmin [@username]\nПример: /setgladmin @username")
        return
    
    username = context.args[0]
    found_users = bot_data.search_user_by_username(username)
    
    if not found_users:
        await update.message.reply_text(f"❌ Пользователь {username} не найден")
        return
    
    target_id, target_data = found_users[0]
    
    bot_data.users[target_id]["is_admin"] = True
    
    admin_username = update.effective_user.username or str(update.effective_user.id)
    bot_data.add_admin_log(user_id, admin_username, "НАЗНАЧЕНИЕ_АДМИНА", target_data["username"])
    
    await update.message.reply_text(f"✅ Пользователь @{target_data['username']} теперь Главный Администратор!")

async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Логи администраторов"""
    user_id = update.effective_user.id
    
    if not bot_data.is_creator_authenticated(user_id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if not bot_data.admin_logs:
        await update.message.reply_text("📝 Логи администраторов пусты.")
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
    
    await update.message.reply_text(response)

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
    
    # Команды авторизации
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("panel", panel))
    application.add_handler(CommandHandler("creatorcmd", creatorcmd))
    
    # Новые команды
    application.add_handler(CommandHandler("setdonate", setdonate))
    application.add_handler(CommandHandler("message", message_cmd))
    
    # Команды для администраторов
    application.add_handler(CommandHandler("givecash", givecash))
    application.add_handler(CommandHandler("givedonate", givedonate))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("unban", unban))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CommandHandler("userinfo", userinfo))
    application.add_handler(CommandHandler("announce", announce))
    
    # Команды только для создателя
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
    logger.info("👑 Создатель бота: Frapello")
    
    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
