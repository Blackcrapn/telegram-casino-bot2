import os
import logging
import random
import time
from typing import Dict, List, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask
from threading import Thread

app = Flask('')
@app.route('/')
def home(): return "🎰 Casino Bot is Running!"
Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))).start()

TOKEN = os.environ.get('TELEGRAM_TOKEN')

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

class CasinoBot:
    def __init__(self):
        # Задаем создателя по username
        self.creator_usernames = {"frapellogello"}  # username без @ в нижнем регистре
        self.users = {}
        self.banned_users = set()
        self.admin_logs = []
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
                "is_admin": is_creator  # Создатель автоматически становится админом
            }
            # Если это создатель, даем бесконечные ресурсы
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
        
        return int(base_win * bonus_multiplier)

    def get_leaderboard(self) -> List[Tuple[int, Dict]]:
        # Исключаем создателя из таблицы лидеров
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
        
        # Храним только последние 50 записей
        if len(self.admin_logs) > 50:
            self.admin_logs.pop(0)

bot_data = CasinoBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены и не можете использовать бота.")
        return
    
    bot_data.init_user(user_id, user.username)
    
    if bot_data.is_creator(user_id):
        await update.message.reply_text(
            f"👑 Добро пожаловать, СОЗДАТЕЛЬ!\n"
            f"👤 Ваш username: @{user.username}\n"
            f"🆔 Ваш ID: `{user_id}`\n\n"
            f"💎 Вам доступны бесконечные монеты и PlayCoin!\n\n"
            f"📋 Основные команды:\n"
            f"/play [ставка] [игра] - начать игру\n"
            f"/shop - магазин привилегий\n"
            f"/leaderboard - таблица лидеров\n"
            f"/stats - ваша статистика\n"
            f"/wheel - колесо удачи (100 PC)\n"
            f"/author - информация об авторе\n\n"
            f"⚙️ Специальные команды создателя:\n"
            f"/givecash [id] [amount] - выдать монеты\n"
            f"/givedonate [id] [donate] - выдать донат\n"
            f"/ban [id] - забанить игрока\n"
            f"/unban [id] - разбанить игрока\n"
            f"/search [@username] - найти ID по юзернейму\n"
            f"/setgladmin [@username] - назначить администратора\n"
            f"/logs - просмотр логов администраторов",
            parse_mode='Markdown'
        )
    elif bot_data.users[user_id].get("is_admin", False):
        await update.message.reply_text(
            f"🔧 Добро пожаловать, Главный Администратор!\n"
            f"👤 Ваш ID: `{user_id}`\n\n"
            f"📋 Основные команды:\n"
            f"/play [ставка] [игра] - начать игру\n"
            f"/shop - магазин привилегий\n"
            f"/leaderboard - таблица лидеров\n"
            f"/stats - ваша статистика\n"
            f"/wheel - колесо удачи (100 PC)\n"
            f"/author - информация об авторе\n\n"
            f"⚙️ Команды администратора:\n"
            f"/givecash [id] [amount] - выдать монеты\n"
            f"/givedonate [id] [donate] - выдать донат\n"
            f"/ban [id] - забанить игрока\n"
            f"/unban [id] - разбанить игрока",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"🎰 Добро пожаловать в казино-бот!\n"
            f"👤 Ваш ID: `{user_id}`\n\n"
            f"📋 Доступные команды:\n"
            f"/play [ставка] [игра] - начать игру\n"
            f"/shop - магазин привилегий\n"
            f"/leaderboard - таблица лидеров\n"
            f"/stats - ваша статистика\n"
            f"/wheel - колесо удачи (100 PC)\n"
            f"/author - информация об авторе",
            parse_mode='Markdown'
        )

# ... (остальные функции setgladmin, logs, search, givecash, givedonate, ban, unban остаются без изменений)
# Копируем их из предыдущего кода без изменений

async def setgladmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not bot_data.is_creator(user_id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
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
    
    # Назначаем администратором
    bot_data.users[target_id]["is_admin"] = True
    
    # Логируем действие
    admin_username = update.effective_user.username or str(update.effective_user.id)
    bot_data.add_admin_log(user_id, admin_username, "НАЗНАЧЕНИЕ_АДМИНА", target_data["username"])
    
    await update.message.reply_text(f"✅ Пользователь @{target_data['username']} теперь Главный Администратор!")

async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not bot_data.is_creator(user_id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
        return
    
    if not bot_data.admin_logs:
        await update.message.reply_text("📝 Логи администраторов пусты.")
        return
    
    response = "📝 ЛОГИ АДМИНИСТРАТОРОВ:\n\n"
    
    for log in reversed(bot_data.admin_logs[-20:]):  # Последние 20 записей
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

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not bot_data.is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администраторам")
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

async def givecash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not bot_data.is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администраторам")
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
    
    # Логируем действие если это не создатель
    if not bot_data.is_creator(user_id):
        admin_username = update.effective_user.username or str(user_id)
        target_username = bot_data.users[target_id]["username"] or str(target_id)
        bot_data.add_admin_log(user_id, admin_username, "ВЫДАЧА_МОНЕТ", target_username, f"{amount} монет")
    
    await update.message.reply_text(f"✅ Баланс пользователя {target_id} пополнен на {amount}")

async def givedonate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not bot_data.is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администраторам")
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
    
    # Логируем действие если это не создатель
    if not bot_data.is_creator(user_id):
        admin_username = update.effective_user.username or str(user_id)
        target_username = bot_data.users[target_id]["username"] or str(target_id)
        bot_data.add_admin_log(user_id, admin_username, "ВЫДАЧА_ДОНАТА", target_username, donate_name)
    
    await update.message.reply_text(f"✅ Пользователю {target_id} выдан донат {donate_name}\n{donate_desc}")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not bot_data.is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администраторам")
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
    
    # Логируем действие если это не создатель
    if not bot_data.is_creator(user_id):
        admin_username = update.effective_user.username or str(user_id)
        target_username = bot_data.users[target_id]["username"] if target_id in bot_data.users else str(target_id)
        bot_data.add_admin_log(user_id, admin_username, "БАН", target_username)
    
    await update.message.reply_text(f"✅ Пользователь {target_id} забанен")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not bot_data.is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администраторам")
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
        
        # Логируем действие если это не создатель
        if not bot_data.is_creator(user_id):
            admin_username = update.effective_user.username or str(user_id)
            target_username = bot_data.users[target_id]["username"] if target_id in bot_data.users else str(target_id)
            bot_data.add_admin_log(user_id, admin_username, "РАЗБАН", target_username)
        
        await update.message.reply_text(f"✅ Пользователь {target_id} разбанен")
    else:
        await update.message.reply_text("❌ Пользователь не забанен")

# ... (остальные функции author, play, wheel, shop, button_handler, buy_privilege, leaderboard, stats остаются без изменений)
# Копируем их из предыдущего кода

async def author(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👨‍💻 Автор бота: Самир")

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "Использование: /play [ставка] [номер игры]\n\n"
            "🎮 Доступные игры:\n"
            "1. 🎡 Рулетка (1-36)\n"
            "2. 🎯 Координаты\n"
            "3. 🪙 Монетка"
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
    
    await update.message.reply_text(result_text)

async def wheel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    
    result = bot_data.spin_wheel(user_id)
    user = bot_data.users[user_id]
    
    result_text = f"{result}\n\n🎯 Осталось PlayCoin: {'∞' if bot_data.is_creator(user_id) else user['play_coins']}"
    await update.message.reply_text(result_text)

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    
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
    
    await query.edit_message_text(
        f"🎉 Поздравляем с покупкой!\n"
        f"Теперь у вас: {priv_info['title']}\n"
        f"Бонус: +{int((priv_info['bonus'] - 1) * 100)}% к выигрышам\n\n"
        f"💰 Остаток: {'∞' if bot_data.is_creator(user_id) else user['balance']}"
    )

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
        username = user_data["username"] or f"Игрок {user_id}"
        privilege_title = ""
        if user_data["privilege"]:
            privilege_title = bot_data.privileges[user_data["privilege"]]["title"]
        
        text += f"{i}. {username} {privilege_title}\n"
        text += f"   💰 Заработано: {user_data['total_earned']}\n\n"
    
    await update.message.reply_text(text)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    
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

def main():
    if not TOKEN:
        print("❌ Токен не найден! Установите переменную TELEGRAM_TOKEN")
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
    
    # Команды для администраторов и создателя
    application.add_handler(CommandHandler("givecash", givecash))
    application.add_handler(CommandHandler("givedonate", givedonate))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("unban", unban))
    application.add_handler(CommandHandler("search", search))
    
    # Команды только для создателя
    application.add_handler(CommandHandler("setgladmin", setgladmin))
    application.add_handler(CommandHandler("logs", logs))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 Бот запущен и работает 24/7!")
    print("👑 Создатель бота: @FrapelloGello")
    application.run_polling()

if __name__ == '__main__':
    main()
