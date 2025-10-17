import os
import logging
import random
import time
import json
import threading
from typing import Dict, List, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from http.server import HTTPServer, BaseHTTPRequestHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Health сервер для Render
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
        self.last_reply_time = {}  # Для отслеживания времени ответов пользователей
        
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
    """Выдает эксклюзивные донаты пользователю"""
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
    """Отправляет сообщение пользователю"""
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
    """Ответить на сообщение создателя/администратора"""
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

# ==================== ОБНОВЛЕННЫЙ ЛИДЕРБОРД ====================

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

# ==================== СУЩЕСТВУЮЩИЕ КОМАНДЫ (с обновленными описаниями) ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сыграть в игру [ставка] [номер игры: Рулетка - 1, Координаты - 2, Монетка - 3]"""
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
            "3. 🪙 Монетка\n\n"
            "Пример: /play 100 1"
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

# ==================== ОСТАЛЬНЫЕ КОМАНДЫ (аналогично обновлены) ====================

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

# ... (остальные команды остаются аналогичными, но с вызовом bot_data.save_data() где необходимо)

# ==================== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ ====================

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
    logger.info("👑 Создатель бота: @FrapelloGello")
    application.run_polling()

if __name__ == '__main__':
    main()
