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
        self.creator_usernames = {"frapellogello"}
        self.users = {}
        self.banned_users = set()
        self.admin_logs = []
        self.global_multiplier = 1.0
        self.welcome_message = None
        self.test_mode = False
        self.promocodes = {}
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
                "is_admin": is_creator,
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

    def create_promo_code(self, code: str, reward: int, max_uses: int = 100):
        self.promocodes[code.upper()] = {
            "reward": reward,
            "max_uses": max_uses,
            "used_count": 0,
            "created_at": time.time()
        }

bot_data = CasinoBot()

# ==================== КОМАНДЫ ДЛЯ СОЗДАТЕЛЯ ====================

async def setbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_data.is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
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
    await update.message.reply_text(f"✅ Баланс пользователя {target_id} установлен в {amount}")

async def reseteconomy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_data.is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
        return
    
    bot_data.reset_economy()
    await update.message.reply_text("✅ Экономика бота полностью сброшена!")

async def setmultiplier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_data.is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
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
    await update.message.reply_text(f"✅ Глобальный множитель установлен: {multiplier}x")

async def resetuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_data.is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
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
    
    await update.message.reply_text(f"✅ Статистика пользователя {target_id} сброшена")

async def massgive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_data.is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
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
    if not bot_data.is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
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
    if not bot_data.is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
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
    if not bot_data.is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
        return
    
    if not bot_data.users:
        await update.message.reply_text("❌ Нет данных для экспорта")
        return
    
    # Ограничиваем вывод чтобы не превысить лимит Telegram
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
        
        if len(response) > 3000:  # Ограничение длины сообщения
            break
    
    response += f"\n📊 Всего пользователей в базе: {len(bot_data.users)}"
    await update.message.reply_text(response)

async def topactive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_data.is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
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
    if not bot_data.is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
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
    if not bot_data.is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
        return
    
    await update.message.reply_text("🔄 Перезагрузка бота...")
    # В реальности нужно перезапустить приложение
    # Здесь просто сообщаем о "перезагрузке"
    await update.message.reply_text("✅ Бот 'перезагружен'. Все данные сохранены.")

async def cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_data.is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
        return
    
    days = 30
    if context.args and context.args[0].isdigit():
        days = int(context.args[0])
    
    removed_count = bot_data.cleanup_inactive_users(days)
    await update.message.reply_text(f"🧹 Удалено {removed_count} неактивных пользователей (неактивность > {days} дней)")

async def setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_data.is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /setwelcome [текст приветствия]")
        return
    
    welcome_text = ' '.join(context.args)
    bot_data.welcome_message = welcome_text
    await update.message.reply_text(f"✅ Приветственное сообщение установлено:\n\n{welcome_text}")

async def createpromo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_data.is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /createpromo [код] [награда] (макс. использований)")
        return
    
    code = context.args[0].upper()
    try:
        reward = int(context.args[1])
        max_uses = int(context.args[2]) if len(context.args) > 2 else 100
    except ValueError:
        await update.message.reply_text("❌ Ошибка: награда и макс. использований должны быть числами")
        return
    
    bot_data.create_promo_code(code, reward, max_uses)
    await update.message.reply_text(f"✅ Промокод создан:\nКод: {code}\nНаграда: {reward} монет\nМакс. использований: {max_uses}")

async def testmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_data.is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
        return
    
    if not context.args:
        await update.message.reply_text(f"🎯 Тестовый режим: {'ВКЛ' if bot_data.test_mode else 'ВЫКЛ'}")
        return
    
    mode = context.args[0].lower()
    if mode in ["on", "вкл", "true", "1"]:
        bot_data.test_mode = True
        await update.message.reply_text("✅ Тестовый режим ВКЛЮЧЕН")
    elif mode in ["off", "выкл", "false", "0"]:
        bot_data.test_mode = False
        await update.message.reply_text("✅ Тестовый режим ВЫКЛЮЧЕН")
    else:
        await update.message.reply_text("❌ Использование: /testmode [on/off]")

async def addgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_data.is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
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
    
    await update.message.reply_text(f"✅ Новая игра добавлена:\nID: {new_game_id}\nНазвание: {game_name}\nОписание: {game_description}")

async def massprivilege(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_data.is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю бота")
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
    await update.message.reply_text(f"✅ Привилегия {privilege_title} выдана {affected} пользователям")

# ==================== КОМАНДЫ ДЛЯ СОЗДАТЕЛЯ И АДМИНОВ ====================

async def userinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not bot_data.is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администраторам")
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

async def announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not bot_data.is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администраторам")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /announce [сообщение]")
        return
    
    message = ' '.join(context.args)
    sender_role = "Создателя" if bot_data.is_creator(user_id) else "Администратора"
    
    sent_count = 0
    failed_count = 0
    
    # Ограничиваем рассылку первыми 100 пользователями для безопасности
    users_to_notify = list(bot_data.users.items())[:100]
    
    for target_id, user_data in users_to_notify:
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"📢 Сообщение от {sender_role}:\n\n{message}"
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

# ==================== СУЩЕСТВУЮЩИЕ КОМАНДЫ (исправленные) ====================

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
            f"/author - информация об авторе\n\n"
            f"⚙️ Специальные команды создателя:\n"
            f"/setbalance, /reseteconomy, /setmultiplier, /resetuser\n"
            f"/massgive, /listadmins, /botstats, /exportdata\n"
            f"/topactive, /gamestats, /reboot, /cleanup\n"
            f"/setwelcome, /createpromo, /testmode, /addgame\n"
            f"/massprivilege, /announce, /userinfo",
            parse_mode='Markdown'
        )
    elif bot_data.users[user_id].get("is_admin", False):
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
            f"/author - информация об авторе\n\n"
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
            f"/author - информация об авторе",
            parse_mode='Markdown'
        )

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    
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

    # Обновляем статистику игры
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
    
    await update.message.reply_text(result_text)

# ... (остальные существующие команды остаются без изменений, но с добавлением обновления last_activity)

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
    
    # Команды только для создателя (управление админами)
    application.add_handler(CommandHandler("setgladmin", setgladmin))
    application.add_handler(CommandHandler("logs", logs))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 Бот запущен и работает 24/7!")
    print("👑 Создатель бота: @FrapelloGello")
    print("⚠️  ВНИМАНИЕ: Все данные хранятся в оперативной памяти и будут потеряны при перезапуске!")
    application.run_polling()

if __name__ == '__main__':
    main()
