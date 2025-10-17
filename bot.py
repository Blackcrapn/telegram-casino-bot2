import os
import logging
import random
import time
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
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

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
        self.admin_passwords = {}
        self.creator_password = "FrapSnick88"
        self.last_response_times = {}  # Время последнего ответа пользователей
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
                "creator_authenticated": False,
                "creator_auth_time": 0,
                "admin_authenticated": False,
                "admin_auth_time": 0,
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
        if not self.is_creator(user_id):
            return False
        auth_time = self.users[user_id].get("creator_auth_time", 0)
        # Проверяем, не прошло ли 24 часа с момента авторизации
        if time.time() - auth_time > 24 * 60 * 60:  # 24 часа
            self.users[user_id]["creator_authenticated"] = False
            return False
        return self.users[user_id].get("creator_authenticated", False)

    def is_admin_authenticated(self, user_id: int) -> bool:
        if self.is_creator_authenticated(user_id):
            return True
        if user_id not in self.users:
            return False
        auth_time = self.users[user_id].get("admin_auth_time", 0)
        # Проверяем, не прошло ли 24 часа с момента авторизации
        if time.time() - auth_time > 24 * 60 * 60:  # 24 часа
            self.users[user_id]["admin_authenticated"] = False
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

    def can_user_respond(self, user_id: int) -> bool:
        """Проверяет, может ли пользователь ответить на сообщение"""
        last_time = self.last_response_times.get(user_id, 0)
        current_time = time.time()
        return current_time - last_time >= 300  # 5 минут

    def update_response_time(self, user_id: int):
        """Обновляет время последнего ответа пользователя"""
        self.last_response_times[user_id] = time.time()

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
        await update.message.reply_text(
            "✅ Авторизация успешна! Теперь вам доступны все команды создателя.\n\n"
            "Используйте /creatorcmd для просмотра всех команд создателя."
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
        await update.message.reply_text(
            f"✅ Пароль установлен! Теперь авторизуйтесь: /panel {password}"
        )
        return
    
    if not context.args:
        await update.message.reply_text("🔐 Авторизуйтесь: /panel [ваш пароль]")
        return
    
    password = context.args[0]
    
    if user_id in bot_data.admin_passwords and bot_data.admin_passwords[user_id] == password:
        bot_data.users[user_id]["admin_authenticated"] = True
        bot_data.users[user_id]["admin_auth_time"] = time.time()
        await update.message.reply_text(
            "✅ Авторизация успешна! Теперь вам доступны команды администратора."
        )
    else:
        await update.message.reply_text("❌ Неверный пароль")

# ==================== НОВЫЕ КОМАНДЫ ====================

async def creatorcmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not bot_data.is_creator(user_id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
        return
    
    if not bot_data.is_creator_authenticated(user_id):
        await update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    commands_text = """
👑 КОМАНДЫ СОЗДАТЕЛЯ:

💰 ЭКОНОМИКА:
/setbalance [ID] [сумма] - установить точный баланс пользователю
/reseteconomy - полностью сбросить экономику бота
/setmultiplier [значение] - установить глобальный множитель выигрышей
/massgive [сумма] [критерий] - массовая выдача монет

👥 УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ:
/resetuser [ID] - сбросить статистику пользователя
/listadmins - список всех администраторов
/setgladmin [@username] - назначить администратора
/setdonate [ID] [донат] - выдать эксклюзивный донат

📊 СТАТИСТИКА:
/botstats - полная статистика бота
/exportdata - экспорт данных пользователей
/topactive [лимит] - самые активные игроки
/gamestats - статистика по играм

⚙️ СИСТЕМНЫЕ:
/reboot - перезагрузка бота
/cleanup [дни] - очистка неактивных пользователей
/setwelcome [текст] - установить приветственное сообщение
/testmode [on/off] - тестовый режим

🎮 ИГРЫ:
/addgame [название] [описание] - добавить новую игру
/massprivilege [привилегия] - массовая выдача привилегии

📢 КОММУНИКАЦИЯ:
/announce [сообщение] - рассылка всем пользователям
/message [ID] [сообщение] - отправить сообщение пользователю
/logs - просмотр логов администраторов
/search [@username] - поиск пользователя по юзернейму
/userinfo [ID] - информация о пользователе

🎁 ПРОМОКОДЫ:
/createpromo [код] [тип] [значение] - создать промокод
    """
    
    await update.message.reply_text(commands_text)

async def setdonate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not (bot_data.is_creator_authenticated(user_id) or bot_data.is_admin_authenticated(user_id)):
        await update.message.reply_text("❌ Авторизуйтесь: /register [пароль] или /panel [пароль]")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("Использование: /setdonate [ID пользователя] [название доната]\n\nДоступные донаты: TITAN, FLE, DRAGON")
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
    
    # Логируем действие если это не создатель
    if not bot_data.is_creator(user_id):
        admin_username = update.effective_user.username or str(user_id)
        target_username = bot_data.users[target_id]["username"] or str(target_id)
        bot_data.add_admin_log(user_id, admin_username, "ВЫДАЧА_ДОНАТА", target_username, donate_name)
    
    await update.message.reply_text(f"✅ Пользователю {target_id} выдан донат {donate_name}\n{donate_desc}")

async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not (bot_data.is_creator_authenticated(user_id) or bot_data.is_admin_authenticated(user_id)):
        await update.message.reply_text("❌ Авторизуйтесь: /register [пароль] или /panel [пароль]")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /message [ID пользователя] [сообщение]")
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
        await context.bot.send_message(
            chat_id=target_id,
            text=f"📨 Сообщение от администрации:\n\n{message_text}"
        )
        await update.message.reply_text(f"✅ Сообщение отправлено пользователю {target_id}")
    except Exception as e:
        await update.message.reply_text(f"❌ Не удалось отправить сообщение: {e}")

async def q(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /q [ваше сообщение]")
        return
    
    if not bot_data.can_user_respond(user_id):
        await update.message.reply_text("❌ Вы можете отправлять ответы только раз в 5 минут")
        return
    
    message_text = ' '.join(context.args)
    user_data = bot_data.users.get(user_id, {})
    username = user_data.get("username", "Неизвестно")
    
    # Отправляем сообщение всем администраторам и создателю
    sent_count = 0
    for admin_id, admin_data in bot_data.users.items():
        if bot_data.is_admin(admin_id) or bot_data.is_creator(admin_id):
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"📩 Ответ от пользователя:\n\n"
                         f"👤 ID: {user_id}\n"
                         f"📛 Username: @{username}\n"
                         f"💬 Сообщение: {message_text}"
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение администратору {admin_id}: {e}")
    
    bot_data.update_response_time(user_id)
    await update.message.reply_text(f"✅ Ваше сообщение отправлено администрации ({sent_count} получателей)")

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

# ==================== ОБНОВЛЕННАЯ КОМАНДА ANNOUNCE ====================

async def announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not (bot_data.is_creator_authenticated(user_id) or bot_data.is_admin_authenticated(user_id)):
        await update.message.reply_text("❌ Авторизуйтесь: /register [пароль] или /panel [пароль]")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /announce [сообщение]")
        return
    
    message = ' '.join(context.args)
    sender_role = "Создателя" if bot_data.is_creator(user_id) else "Администратора"
    
    sent_count = 0
    failed_count = 0
    
    users_to_notify = list(bot_data.users.items())[:100]  # Ограничиваем для безопасности
    
    for target_id, user_data in users_to_notify:
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"📢 Сообщение от {sender_role}:\n\n{message}\n\n"
                     f"💬 Ответить: /q [ваше сообщение] (раз в 5 минут)"
            )
            sent_count += 1
            time.sleep(0.1)  # Задержка чтобы не превысить лимиты Telegram
        except Exception as e:
            failed_count += 1
            logging.error(f"Не удалось отправить сообщение пользователю {target_id}: {e}")
    
    await update.message.reply_text(
        f"✅ Рассылка завершена:\n"
        f"• Отправлено: {sent_count}\n"
        f"• Не удалось: {failed_count}\n"
        f"• Всего пользователей в базе: {len(bot_data.users)}"
    )

# ==================== ОСНОВНЫЕ КОМАНДЫ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены и не можете использовать бота.")
        return
    
    bot_data.init_user(user_id, user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    
    welcome_text = bot_data.welcome_message or "🎰 Добро пожаловать в PlayBot!"
    
    if bot_data.is_creator(user_id):
        if not bot_data.is_creator_authenticated(user_id):
            await update.message.reply_text(
                f"👑 Добро пожаловать, СОЗДАТЕЛЬ!\n"
                f"{welcome_text}\n\n"
                f"👤 Ваш username: @{user.username}\n"
                f"🆔 Ваш ID: `{user_id}`\n\n"
                f"🔐 Авторизуйтесь: /register [пароль]\n\n"
                f"📋 Основные команды:\n"
                f"/play - сыграть в игру [ставка] [номер игры: Рулетка - 1, Координаты - 2, Монетка - 3]\n"
                f"/shop - магазин привилегий\n"
                f"/leaderboard - таблица лидеров\n"
                f"/stats - ваша статистика\n"
                f"/wheel - колесо удачи (100 PC)\n"
                f"/author - информация об авторе\n"
                f"/promo - активировать промокод [код]\n"
                f"/repriv - сменить привилегию [название]",
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
                f"/play - сыграть в игру [ставка] [номер игры: Рулетка - 1, Координаты - 2, Монетка - 3]\n"
                f"/shop - магазин привилегий\n"
                f"/leaderboard - таблица лидеров\n"
                f"/stats - ваша статистика\n"
                f"/wheel - колесо удачи (100 PC)\n"
                f"/author - информация об авторе\n"
                f"/promo - активировать промокод [код]\n"
                f"/repriv - сменить привилегию [название]\n\n"
                f"⚙️ Команды создателя:\n"
                f"/creatorcmd - просмотр всех команд создателя",
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
                f"/play - сыграть в игру [ставка] [номер игры: Рулетка - 1, Координаты - 2, Монетка - 3]\n"
                f"/shop - магазин привилегий\n"
                f"/leaderboard - таблица лидеров\n"
                f"/stats - ваша статистика\n"
                f"/wheel - колесо удачи (100 PC)\n"
                f"/author - информация об авторе\n"
                f"/promo - активировать промокод [код]\n"
                f"/repriv - сменить привилегию [название]",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"🔧 Добро пожаловать, Администратор!\n"
                f"{welcome_text}\n\n"
                f"👤 Ваш ID: `{user_id}`\n\n"
                f"📋 Основные команды:\n"
                f"/play - сыграть в игру [ставка] [номер игры: Рулетка - 1, Координаты - 2, Монетка - 3]\n"
                f"/shop - магазин привилегий\n"
                f"/leaderboard - таблица лидеров\n"
                f"/stats - ваша статистика\n"
                f"/wheel - колесо удачи (100 PC)\n"
                f"/author - информация об авторе\n"
                f"/promo - активировать промокод [код]\n"
                f"/repriv - сменить привилегию [название]\n\n"
                f"⚙️ Команды администратора:\n"
                f"/givecash - выдать монеты [ID] [сумма]\n"
                f"/givedonate - выдать донат [ID] [донат]\n"
                f"/ban - забанить игрока [ID]\n"
                f"/unban - разбанить игрока [ID]\n"
                f"/search - найти пользователя [@username]\n"
                f"/announce - рассылка сообщений [текст]\n"
                f"/userinfo - информация о пользователе [ID]\n"
                f"/setdonate - выдать донат [ID] [донат]\n"
                f"/message - отправить сообщение [ID] [текст]",
                parse_mode='Markdown'
            )
    
    else:
        await update.message.reply_text(
            f"{welcome_text}\n\n"
            f"👤 Ваш ID: `{user_id}`\n\n"
            f"📋 Доступные команды:\n"
            f"/play - сыграть в игру [ставка] [номер игры: Рулетка - 1, Координаты - 2, Монетка - 3]\n"
            f"/shop - магазин привилегий\n"
            f"/leaderboard - таблица лидеров\n"
            f"/stats - ваша статистика\n"
            f"/wheel - колесо удачи (100 PC)\n"
            f"/author - информация об авторе\n"
            f"/promo - активировать промокод [код]\n"
            f"/repriv - сменить привилегию [название]\n"
            f"/q - ответить администрации [сообщение]",
            parse_mode='Markdown'
        )

# ... (остальной код без изменений: play, wheel, shop, button_handler, buy_privilege, 
# leaderboard, stats, setgladmin, logs, search, givecash, givedonate, ban, unban, 
# userinfo, author, createpromo, setbalance, reseteconomy, setmultiplier, resetuser, 
# massgive, listadmins, botstats, exportdata, topactive, gamestats, reboot, cleanup, 
# setwelcome, testmode, addgame, massprivilege)

# Обновите функцию leaderboard чтобы показывать username
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
        username = f"@{user_data['username']}" if user_data['username'] else f"ID: {user_id}"
        privilege_title = ""
        if user_data["privilege"]:
            privilege_title = bot_data.privileges[user_data["privilege"]]["title"]
        
        text += f"{i}. {username} {privilege_title}\n"
        text += f"   💰 Заработано: {user_data['total_earned']}\n\n"
    
    await update.message.reply_text(text)

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
    
    # Команды для администраторов
    application.add_handler(CommandHandler("givecash", givecash))
    application.add_handler(CommandHandler("givedonate", givedonate))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("unban", unban))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CommandHandler("userinfo", userinfo))
    application.add_handler(CommandHandler("announce", announce))
    application.add_handler(CommandHandler("setdonate", setdonate))
    application.add_handler(CommandHandler("message", message))
    
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
    
    # Команды только для создателя (управление админами)
    application.add_handler(CommandHandler("setgladmin", setgladmin))
    application.add_handler(CommandHandler("logs", logs))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("🤖 Бот запущен и работает 24/7!")
    logger.info("👑 Создатель бота: @FrapelloGello")
    application.run_polling()

if __name__ == '__main__':
    main()
