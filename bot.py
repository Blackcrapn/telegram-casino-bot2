import os
import logging
import random
import time
import json
import threading
import atexit
import signal
from typing import Dict, List, Tuple, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Health server для Render
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
    logger.info(f"Health server running on port {port}")
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TOKEN:
    logger.error("TELEGRAM_TOKEN not set!")
    raise ValueError("TELEGRAM_TOKEN not found")

class CasinoBot:
    def __init__(self):
        self.data_file = "bot_data.json"
        self.social_file = "social_data.json"
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
        
        # Социальные функции
        self.friends_requests = {}
        self.friends = {}
        self.clubs = {}
        self.user_clubs = {}
        self.club_chats = {}
        self.club_safes = {}
        self.test_mode_users = {}
        self.pending_withdrawals = {}
        
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
        self.load_social_data()
        self.setup_emergency_save()

    def setup_emergency_save(self):
        def emergency_handler():
            try:
                logger.info("🔄 Emergency save...")
                self.save_data()
                self.save_social_data()
                logger.info("✅ Emergency save completed")
            except Exception as e:
                logger.error(f"❌ Emergency save failed: {e}")
        
        def signal_handler(signum, frame):
            logger.info(f"📦 Signal {signum} received")
            emergency_handler()
            exit(0)
        
        atexit.register(emergency_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        logger.info("🛡️ Emergency save activated")

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
            logger.info("💾 Data saved")
        except Exception as e:
            logger.error(f"❌ Save error: {e}")

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
                self.last_reply_time = {int(k): v for k, v in self.last_reply_time.items()}
                
                logger.info("💾 Data loaded")
            else:
                logger.info("📝 New database created")
        except Exception as e:
            logger.error(f"❌ Load error: {e}")

    def save_social_data(self):
        try:
            data = {
                'friends_requests': self.friends_requests,
                'friends': self.friends,
                'clubs': self.clubs,
                'user_clubs': self.user_clubs,
                'club_chats': self.club_chats,
                'club_safes': self.club_safes,
                'test_mode_users': self.test_mode_users,
                'pending_withdrawals': self.pending_withdrawals
            }
            with open(self.social_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("💾 Social data saved")
        except Exception as e:
            logger.error(f"❌ Social save error: {e}")

    def load_social_data(self):
        try:
            if os.path.exists(self.social_file):
                with open(self.social_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.friends_requests = data.get('friends_requests', {})
                self.friends = data.get('friends', {})
                self.clubs = data.get('clubs', {})
                self.user_clubs = data.get('user_clubs', {})
                self.club_chats = data.get('club_chats', {})
                self.club_safes = data.get('club_safes', {})
                self.test_mode_users = data.get('test_mode_users', {})
                self.pending_withdrawals = data.get('pending_withdrawals', {})
                
                # Convert keys to int
                self.friends_requests = {int(k): {int(k2): v2 for k2, v2 in v.items()} for k, v in self.friends_requests.items()}
                self.friends = {int(k): v for k, v in self.friends.items()}
                self.user_clubs = {int(k): v for k, v in self.user_clubs.items()}
                self.test_mode_users = {int(k): v for k, v in self.test_mode_users.items()}
                self.pending_withdrawals = {int(k): v for k, v in self.pending_withdrawals.items()}
                
                logger.info("💾 Social data loaded")
            else:
                logger.info("📝 New social database created")
        except Exception as e:
            logger.error(f"❌ Social load error: {e}")

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
        if user_id not in self.users: return False
        username = self.users[user_id].get("username")
        return username and username.lower() in self.creator_usernames

    def is_admin(self, user_id: int) -> bool:
        return self.is_creator(user_id) or (user_id in self.users and self.users[user_id]["is_admin"])

    def is_banned(self, user_id: int) -> bool:
        return user_id in self.banned_users

    # Социальные методы
    def add_friend_request(self, from_user_id: int, to_user_id: int):
        if to_user_id not in self.friends_requests:
            self.friends_requests[to_user_id] = {}
        self.friends_requests[to_user_id][from_user_id] = time.time()
        self.save_social_data()

    def accept_friend_request(self, user_id: int, from_user_id: int):
        if user_id not in self.friends: self.friends[user_id] = []
        if from_user_id not in self.friends: self.friends[from_user_id] = []
        
        if from_user_id not in self.friends[user_id]:
            self.friends[user_id].append(from_user_id)
        if user_id not in self.friends[from_user_id]:
            self.friends[from_user_id].append(user_id)
        
        if user_id in self.friends_requests and from_user_id in self.friends_requests[user_id]:
            del self.friends_requests[user_id][from_user_id]
        self.save_social_data()

    def search_user_by_username(self, username: str) -> List[Tuple[int, Dict]]:
        found_users = []
        username = username.lower().replace('@', '')
        for user_id, user_data in self.users.items():
            if user_data["username"] and user_data["username"].lower() == username:
                found_users.append((user_id, user_data))
        return found_users

    # Игровые методы
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
        filtered_users = {uid: data for uid, data in self.users.items() if not self.is_creator(uid)}
        sorted_users = sorted(filtered_users.items(), key=lambda x: x[1]["total_earned"], reverse=True)
        return sorted_users[:10]

bot_data = CasinoBot()

# ОСНОВНЫЕ КОМАНДЫ
def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    bot_data.init_user(user_id, update.effective_user.username)
    welcome = bot_data.welcome_message or "🎰 Добро пожаловать в казино-бот!"
    update.message.reply_text(f"{welcome}\n\n/help - список команд")

def help_cmd(update: Update, context: CallbackContext):
    help_text = """
🤖 **ОСНОВНЫЕ КОМАНДЫ:**

🎮 **Игры:**
/play [ставка] [игра] - сыграть в игру

💰 **Экономика:**
/balance - ваш баланс
/daily - ежедневная награда

📊 **Информация:**
/stats - ваша статистика  
/leaderboard - таблица лидеров

👥 **Социальные:**
/addfriend [ID] - добавить друга
/createclub [название] - создать клуб
    """
    update.message.reply_text(help_text, parse_mode='Markdown')

def balance(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    bot_data.init_user(user_id, update.effective_user.username)
    user = bot_data.users[user_id]
    update.message.reply_text(f"💰 Баланс: {user['balance']}\n🎯 PlayCoin: {user['play_coins']}")

def play(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    if len(context.args) != 2:
        update.message.reply_text("Использование: /play [ставка] [игра]\n\nИгры: 1-🎡, 2-🎯, 3-🪙, 4-🍀")
        return

    try:
        bet = int(context.args[0])
        game_id = int(context.args[1])
    except ValueError:
        update.message.reply_text("❌ Ставка и номер игры должны быть числами")
        return

    if game_id not in bot_data.games:
        update.message.reply_text("❌ Игра не найдена")
        return

    bot_data.init_user(user_id, update.effective_user.username)
    user = bot_data.users[user_id]
    
    if not bot_data.is_creator(user_id) and bet > user["balance"]:
        update.message.reply_text("❌ Недостаточно средств")
        return

    if bet <= 0:
        update.message.reply_text("❌ Ставка должна быть положительной")
        return

    # Логика игры
    bot_data.game_statistics[game_id]["plays"] += 1
    bot_data.game_statistics[game_id]["total_bets"] += bet
    
    if not bot_data.is_creator(user_id):
        user["balance"] -= bet
    
    user["games_played"] += 1

    won = random.choice([True, False])
    if won:
        win_amount = bet * 2
        bonus_win = bot_data.check_privilege_bonus(user_id, win_amount)
        
        if not bot_data.is_creator(user_id):
            user["balance"] += bonus_win
            user["total_earned"] += bonus_win
        
        user["last_win"] = True
        user["win_streak"] += 1
        bot_data.game_statistics[game_id]["total_wins"] += 1
        
        result_text = f"🎉 Поздравляем! Вы выиграли {bonus_win}!"
    else:
        user["last_win"] = False
        user["win_streak"] = 0
        result_text = "❌ Вы проиграли."

    result_text += f"\n\n💰 Баланс: {'∞' if bot_data.is_creator(user_id) else user['balance']}"
    result_text += f"\n🔥 Серия побед: {user['win_streak']}"
    
    bot_data.save_data()
    update.message.reply_text(result_text)

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
    
    reward = 5000
    user["balance"] += reward
    user["last_daily"] = current_time
    user["daily_streak"] = user.get("daily_streak", 0) + 1
    user["total_earned"] += reward
    
    bot_data.save_data()
    update.message.reply_text(f"🎁 Ежедневная награда: +{reward}💰\n💳 Баланс: {user['balance']}")

def stats(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    user = bot_data.users[user_id]
    
    update.message.reply_text(
        f"📊 Ваша статистика\n\n"
        f"💰 Баланс: {user['balance']}\n"
        f"🎯 PlayCoin: {user['play_coins']}\n"
        f"🎮 Сыграно игр: {user['games_played']}\n"
        f"🏆 Всего заработано: {user['total_earned']}\n"
        f"🔥 Серия побед: {user['win_streak']}"
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
        text += f"{i}. {username}\n"
        text += f"   💰 Заработано: {user_data['total_earned']}\n\n"
    
    update.message.reply_text(text)

# СОЦИАЛЬНЫЕ КОМАНДЫ
def addfriend(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    if not context.args:
        update.message.reply_text("Использование: /addfriend [ID пользователя]")
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        update.message.reply_text("❌ ID должен быть числом")
        return
    
    if target_id not in bot_data.users:
        update.message.reply_text("❌ Пользователь не найден")
        return
    
    if target_id == user_id:
        update.message.reply_text("❌ Нельзя добавить себя в друзья")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.init_user(target_id, bot_data.users[target_id]["username"])
    
    # Проверяем, не отправил ли уже запрос
    if target_id in bot_data.friends_requests and user_id in bot_data.friends_requests[target_id]:
        update.message.reply_text("❌ Вы уже отправили запрос этому пользователю")
        return
    
    # Проверяем, уже ли друзья
    if user_id in bot_data.friends and target_id in bot_data.friends[user_id]:
        update.message.reply_text("❌ Этот пользователь уже у вас в друзьях")
        return
    
    # Отправляем запрос
    bot_data.add_friend_request(user_id, target_id)
    
    # Создаем кнопки для получателя
    keyboard = [
        [
            InlineKeyboardButton("✅ Принять", callback_data=f"friend_accept_{user_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"friend_reject_{user_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        # Отправляем запрос получателю
        requester_username = bot_data.users[user_id]["username"] or f"ID:{user_id}"
        context.bot.send_message(
            chat_id=target_id,
            text=f"👥 Запрос в друзья от @{requester_username}\n\nХотите принять запрос?",
            reply_markup=reply_markup
        )
        update.message.reply_text("✅ Запрос в друзья отправлен!")
    except Exception as e:
        update.message.reply_text("❌ Не удалось отправить запрос")

def createclub(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    if not context.args:
        update.message.reply_text("Использование: /createclub [название]")
        return
    
    club_name = context.args[0]
    
    bot_data.init_user(user_id, update.effective_user.username)
    user = bot_data.users[user_id]
    
    # Проверяем стоимость
    if user["play_coins"] < 200 and user["balance"] < 5000000:
        update.message.reply_text("❌ Недостаточно средств. Нужно 200 PlayCoin ИЛИ 5,000,000 монет")
        return
    
    # Проверяем, существует ли клуб
    if club_name in bot_data.clubs:
        update.message.reply_text("❌ Клуб с таким названием уже существует")
        return
    
    # Создаем клуб
    bot_data.clubs[club_name] = {
        "owner": user_id,
        "members": {user_id: {"rank": 6, "joined_at": time.time()}},
        "ranks": ["Новичок", "Участник", "Активный", "Офицер", "Вице-лидер"],
        "created_at": time.time(),
        "description": ""
    }
    
    # Добавляем в пользовательские клубы
    if user_id not in bot_data.user_clubs:
        bot_data.user_clubs[user_id] = []
    bot_data.user_clubs[user_id].append(club_name)
    
    # Инициализация чата и сейфа
    bot_data.club_chats[club_name] = []
    bot_data.club_safes[club_name] = {"balance": 0, "transactions": []}
    
    # Списание средств
    if user["play_coins"] >= 200:
        user["play_coins"] -= 200
        cost_text = "200 PlayCoin"
    else:
        user["balance"] -= 5000000
        cost_text = "5,000,000 монет"
    
    bot_data.save_data()
    bot_data.save_social_data()
    
    update.message.reply_text(f"✅ Клуб '{club_name}' создан за {cost_text}!\nИспользуйте /club для информации")

# ОБРАБОТЧИК КНОПОК
def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if bot_data.is_banned(user_id):
        query.edit_message_text("❌ Вы забанены.")
        return
    
    # Обработка запросов в друзья
    if data.startswith("friend_accept_"):
        from_user_id = int(data.split("_")[2])
        bot_data.accept_friend_request(user_id, from_user_id)
        query.edit_message_text("✅ Запрос в друзья принят!")
        
        # Уведомляем отправителя
        try:
            requester_username = bot_data.users[user_id]["username"] or f"ID:{user_id}"
            context.bot.send_message(
                chat_id=from_user_id,
                text=f"✅ @{requester_username} принял(а) ваш запрос в друзья!"
            )
        except: pass
    
    elif data.startswith("friend_reject_"):
        from_user_id = int(data.split("_")[2])
        bot_data.reject_friend_request(user_id, from_user_id)
        query.edit_message_text("❌ Запрос в друзья отклонен")

def main():
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher
    
    # Основные команды
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_cmd))
    dispatcher.add_handler(CommandHandler("balance", balance))
    dispatcher.add_handler(CommandHandler("play", play))
    dispatcher.add_handler(CommandHandler("daily", daily))
    dispatcher.add_handler(CommandHandler("stats", stats))
    dispatcher.add_handler(CommandHandler("leaderboard", leaderboard))
    
    # Социальные команды
    dispatcher.add_handler(CommandHandler("addfriend", addfriend))
    dispatcher.add_handler(CommandHandler("createclub", createclub))
    
    # Обработчики кнопок
    dispatcher.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("🤖 Бот запущен и работает!")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
