import os
import logging
import random
import time
import json
import threading
from typing import Dict, List, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
        
        self.friends_requests = {}
        self.friends = {}
        self.friends_names = {}
        
        self.clubs = {}
        self.club_ranks = {}
        self.club_messages = {}
        self.club_join_requests = {}
        
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
        
        self.auto_save_thread = threading.Thread(target=self.auto_save, daemon=True)
        self.auto_save_thread.start()
        
        self.load_data()

    def auto_save(self):
        while True:
            time.sleep(300)
            self.save_data()

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
                'last_reply_time': self.last_reply_time,
                'friends_requests': self.friends_requests,
                'friends': self.friends,
                'friends_names': self.friends_names,
                'clubs': self.clubs,
                'club_ranks': self.club_ranks,
                'club_messages': self.club_messages,
                'club_join_requests': self.club_join_requests
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
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
                
                self.friends_requests = data.get('friends_requests', {})
                self.friends = data.get('friends', {})
                self.friends_names = data.get('friends_names', {})
                self.clubs = data.get('clubs', {})
                self.club_ranks = data.get('club_ranks', {})
                self.club_messages = data.get('club_messages', {})
                self.club_join_requests = data.get('club_join_requests', {})
                
                self.users = {int(k): v for k, v in self.users.items()}
                
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
                "bank_accounts": [],
                "club": None,
                "club_rank": 0
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
        
        elif promo["reward_type"] == "temp_privilege":
            privilege = promo["value"]
            duration = promo["duration"]
            if privilege in self.privileges:
                user["temp_privilege"] = {
                    "name": privilege,
                    "expires": time.time() + duration * 3600
                }
                rewards.append(f"Временная привилегия: {self.privileges[privilege]['title']} на {duration} часов")
        
        self.save_data()
        return f"🎉 Промокод успешно активирован ✅\nПолучены: **{', '.join(rewards)}**"

    def change_privilege(self, user_id: int, new_privilege: str) -> str:
        user = self.users[user_id]
        
        if new_privilege in self.privileges:
            user["privilege"] = new_privilege
            user["temp_privilege"] = None
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

    def add_friend_request(self, from_user_id: int, to_user_id: int):
        if to_user_id not in self.friends_requests:
            self.friends_requests[to_user_id] = {}
        
        from_username = self.users[from_user_id]["username"] or str(from_user_id)
        self.friends_requests[to_user_id][from_user_id] = {
            "timestamp": time.time(),
            "username": from_username
        }
        self.save_data()

    def accept_friend_request(self, user_id: int, from_user_id: int, context: CallbackContext = None):
        if user_id in self.friends_requests and from_user_id in self.friends_requests[user_id]:
            if user_id not in self.friends:
                self.friends[user_id] = []
            if from_user_id not in self.friends:
                self.friends[from_user_id] = []
            
            if from_user_id not in self.friends[user_id]:
                self.friends[user_id].append(from_user_id)
                
            if user_id not in self.friends[from_user_id]:
                self.friends[from_user_id].append(user_id)
            
            from_username = self.users[from_user_id]["username"] or f"Пользователь {from_user_id}"
            user_username = self.users[user_id]["username"] or f"Пользователь {user_id}"
            
            if user_id not in self.friends_names:
                self.friends_names[user_id] = {}
            if from_user_id not in self.friends_names:
                self.friends_names[from_user_id] = {}
                
            self.friends_names[user_id][from_user_id] = from_username
            self.friends_names[from_user_id][user_id] = user_username
            
            del self.friends_requests[user_id][from_user_id]
            if not self.friends_requests[user_id]:
                del self.friends_requests[user_id]
            
            self.save_data()
            
            if context:
                try:
                    context.bot.send_message(
                        chat_id=from_user_id,
                        text=f"✅ Пользователь @{user_username} (ID: {user_id}) принял ваш запрос в друзья!"
                    )
                except Exception:
                    pass
            
            return True
        return False

    def send_message_to_friend(self, user_id: int, friend_name: str, message: str):
        if user_id not in self.friends_names:
            return "❌ У вас нет друзей"
        
        friend_id = None
        for fid, name in self.friends_names[user_id].items():
            if name.lower() == friend_name.lower():
                friend_id = fid
                break
        
        if not friend_id:
            return "❌ Друг с таким именем не найден"
        
        if friend_id not in self.users:
            return "❌ Друг не найден в системе"
        
        return friend_id

    def create_club(self, user_id: int, club_name: str):
        user = self.users[user_id]
        if user["play_coins"] < 200 and user["balance"] < 5000000:
            return "❌ Недостаточно средств. Нужно 200 PlayCoin или 5,000,000 монет"
        
        if club_name in self.clubs:
            return "❌ Клуб с таким названием уже существует"
        
        self.clubs[club_name] = {
            "creator": user_id,
            "members": [user_id],
            "safe_balance": 0,
            "level": 0,
            "created_at": time.time(),
            "last_salary_time": 0
        }
        
        self.club_ranks[club_name] = {
            1: "Новичок",
            2: "Участник", 
            3: "Активный",
            4: "Опытный",
            5: "Ветеран",
            6: "Создатель Клуба"
        }
        
        self.club_messages[club_name] = []
        
        if user["play_coins"] >= 200:
            user["play_coins"] -= 200
        else:
            user["balance"] -= 5000000
        
        user["club"] = club_name
        user["club_rank"] = 6
        
        self.save_data()
        return f"✅ Клуб '{club_name}' успешно создан!"

    def club_salary_distribution(self):
        current_time = time.time()
        
        for club_name, club_data in self.clubs.items():
            if current_time - club_data["last_salary_time"] < 9000:
                continue
            
            salary_amounts = {
                1: 20000,
                2: 50000,  
                3: 250000
            }
            
            salary = salary_amounts.get(club_data["level"], 0)
            if salary > 0:
                for member_id in club_data["members"]:
                    if member_id in self.users:
                        self.users[member_id]["balance"] += salary
                
                club_data["last_salary_time"] = current_time
        
        self.save_data()

    def set_club_rank(self, user_id: int, target_id: int, rank: int):
        user = self.users[user_id]
        if "club" not in user or not user["club"]:
            return "❌ Вы не состоите в клубе"
        
        club_name = user["club"]
        club_data = self.clubs[club_name]
        
        if club_data["creator"] != user_id:
            return "❌ Только создатель клуба может выдавать ранги"
        
        if target_id not in club_data["members"]:
            return "❌ Пользователь не состоит в вашем клубе"
        
        if rank < 1 or rank > 5:
            return "❌ Ранг должен быть от 1 до 5"
        
        self.users[target_id]["club_rank"] = rank
        self.save_data()
        
        target_username = self.users[target_id]["username"] or str(target_id)
        rank_name = self.club_ranks[club_name][rank]
        
        return f"✅ Пользователю @{target_username} установлен ранг: {rank_name}"

    def send_club_message(self, user_id: int, message: str, context: CallbackContext = None):
        user = self.users[user_id]
        if "club" not in user or not user["club"]:
            return "❌ Вы не состоите в клубе"
        
        club_name = user["club"]
        username = user["username"] or str(user_id)
        rank_name = self.club_ranks[club_name][user["club_rank"]]
        
        if club_name not in self.club_messages:
            self.club_messages[club_name] = []
        
        self.club_messages[club_name].append({
            "user_id": user_id,
            "username": username,
            "rank": rank_name,
            "message": message,
            "timestamp": time.time()
        })
        
        if len(self.club_messages[club_name]) > 100:
            self.club_messages[club_name].pop(0)
        
        self.save_data()
        
        formatted_message = f"💬 [{rank_name}] @{username}:\n{message}"
        
        sent_count = 0
        for member_id in self.clubs[club_name]["members"]:
            if member_id != user_id and member_id in self.users:
                try:
                    context.bot.send_message(
                        chat_id=member_id,
                        text=formatted_message
                    )
                    sent_count += 1
                except Exception:
                    pass
        
        return f"✅ Сообщение отправлено {sent_count} участникам клуба"

    def deposit_to_club_safe(self, user_id: int, amount: int, message: str = ""):
        user = self.users[user_id]
        if "club" not in user or not user["club"]:
            return "❌ Вы не состоите в клубе"
        
        if amount <= 0:
            return "❌ Сумма должна быть положительной"
        
        if user["balance"] < amount:
            return "❌ Недостаточно средств на основном балансе"
        
        club_name = user["club"]
        
        user["balance"] -= amount
        self.clubs[club_name]["safe_balance"] += amount
        
        username = user["username"] or str(user_id)
        notification = f"💰 @{username} положил в сейф клуба {amount} монет"
        if message:
            notification += f"\n💬 Сообщение: {message}"
        
        if club_name not in self.club_messages:
            self.club_messages[club_name] = []
        
        self.club_messages[club_name].append({
            "user_id": user_id,
            "username": "🤖 Бот",
            "rank": "Система",
            "message": notification,
            "timestamp": time.time()
        })
        
        self.save_data()
        return f"✅ Успешно положено {amount} монет в сейф клуба"

    def withdraw_from_club_safe(self, user_id: int, amount: int):
        user = self.users[user_id]
        if "club" not in user or not user["club"]:
            return "❌ Вы не состоите в клубе"
        
        club_name = user["club"]
        club_data = self.clubs[club_name]
        
        if club_data["creator"] != user_id:
            return "❌ Только создатель клуба может брать деньги из сейфа"
        
        if amount <= 0:
            return "❌ Сумма должна быть положительной"
        
        if club_data["safe_balance"] < amount:
            return f"❌ Недостаточно средств в сейфе. Доступно: {club_data['safe_balance']}"
        
        club_data["safe_balance"] -= amount
        user["balance"] += amount
        
        self.save_data()
        return f"✅ Успешно взято {amount} монет из сейфа клуба"

    def buy_club_level(self, user_id: int, level: int):
        user = self.users[user_id]
        if "club" not in user or not user["club"]:
            return "❌ Вы не состоите в клубе"
        
        club_name = user["club"]
        club_data = self.clubs[club_name]
        
        if club_data["creator"] != user_id:
            return "❌ Только создатель клуба может покупать уровни"
        
        level_costs = {
            1: 2000000,
            2: 5000000,
            3: 10000000
        }
        
        if level not in level_costs:
            return "❌ Доступные уровни: 1, 2, 3"
        
        cost = level_costs[level]
        
        if club_data["safe_balance"] < cost:
            return f"❌ Недостаточно средств в сейфе. Нужно: {cost}, доступно: {club_data['safe_balance']}"
        
        club_data["safe_balance"] -= cost
        club_data["level"] = level
        
        self.save_data()
        return f"✅ Уровень клуба повышен до {level}! Стоимость: {cost} монет"

    def add_member_to_club(self, user_id: int, target_input: str):
        user = self.users[user_id]
        if "club" not in user or not user["club"]:
            return "❌ Вы не состоите в клубе"
        
        club_name = user["club"]
        club_data = self.clubs[club_name]
        
        if club_data["creator"] != user_id:
            return "❌ Только создатель клуба может добавлять участников"
        
        target_user = None
        target_id = None
        
        if target_input.isdigit():
            target_id = int(target_input)
            if target_id in self.users:
                target_user = self.users[target_id]
        
        if not target_user and target_input.startswith('@'):
            found_users = self.search_user_by_username(target_input[1:])
            if found_users:
                target_id, target_user = found_users[0]
        
        if not target_user:
            found_users = self.search_user_by_username(target_input)
            if found_users:
                target_id, target_user = found_users[0]
        
        if not target_user:
            return "❌ Пользователь не найден"
        
        if self.is_banned(target_id):
            return "❌ Нельзя добавить забаненного пользователя"
        
        if "club" in target_user and target_user["club"]:
            return "❌ Пользователь уже состоит в клубе"
        
        if club_name not in self.club_join_requests:
            self.club_join_requests[club_name] = {}
        
        self.club_join_requests[club_name][target_id] = {
            "timestamp": time.time(),
            "from_user": user_id
        }
        
        self.save_data()
        return target_id

    def accept_club_invite(self, user_id: int, club_name: str, context: CallbackContext = None):
        if club_name not in self.club_join_requests or user_id not in self.club_join_requests[club_name]:
            return False, "❌ Приглашение не найдено или устарело"
        
        from_user_id = self.club_join_requests[club_name][user_id]["from_user"]
        
        self.clubs[club_name]["members"].append(user_id)
        self.users[user_id]["club"] = club_name
        self.users[user_id]["club_rank"] = 1
        
        del self.club_join_requests[club_name][user_id]
        if not self.club_join_requests[club_name]:
            del self.club_join_requests[club_name]
        
        self.save_data()
        
        if context:
            try:
                from_username = self.users[from_user_id]["username"] or str(from_user_id)
                user_username = self.users[user_id]["username"] or str(user_id)
                
                context.bot.send_message(
                    chat_id=from_user_id,
                    text=f"✅ Пользователь @{user_username} (ID: {user_id}) принял ваше приглашение в клуб '{club_name}'!"
                )
                
                club_message = f"🎉 @{user_username} (ID: {user_id}) вступил в клуб!"
                for member_id in self.clubs[club_name]["members"]:
                    if member_id != user_id:
                        try:
                            context.bot.send_message(
                                chat_id=member_id,
                                text=club_message
                            )
                        except Exception:
                            pass
            except Exception:
                pass
        
        return True, "✅ Вы вступили в клуб!"

    def leave_club(self, user_id: int):
        user = self.users[user_id]
        if "club" not in user or not user["club"]:
            return "❌ Вы не состоите в клубе"
        
        club_name = user["club"]
        club_data = self.clubs[club_name]
        
        if club_data["creator"] == user_id:
            for member_id in club_data["members"]:
                if member_id in self.users:
                    self.users[member_id]["club"] = None
                    self.users[member_id]["club_rank"] = 0
            
            del self.clubs[club_name]
            if club_name in self.club_ranks:
                del self.club_ranks[club_name]
            if club_name in self.club_messages:
                del self.club_messages[club_name]
            
            self.save_data()
            return f"✅ Клуб '{club_name}' распущен, так как создатель вышел"
        else:
            club_data["members"].remove(user_id)
            user["club"] = None
            user["club_rank"] = 0
            
            self.save_data()
            return f"✅ Вы вышли из клуба '{club_name}'"

    def get_club_info(self, club_name: str):
        if club_name not in self.clubs:
            return "❌ Клуб не найден"
        
        club_data = self.clubs[club_name]
        creator_username = self.users[club_data["creator"]]["username"] or str(club_data["creator"])
        
        info = f"🏢 **КЛУБ: {club_name}**\n\n"
        info += f"👑 Создатель: @{creator_username}\n"
        info += f"👥 Участников: {len(club_data['members'])}\n"
        info += f"💰 Сейф: {club_data['safe_balance']} монет\n"
        info += f"📊 Уровень: {club_data['level']}\n"
        info += f"⏰ Создан: {time.strftime('%Y-%m-%d %H:%M', time.localtime(club_data['created_at']))}\n"
        
        salary_info = {
            1: "20,000 каждые 2.5ч (требуется 2M в сейфе)",
            2: "50,000 каждые 2.5ч (требуется 5M в сейфе)", 
            3: "250,000 каждые 2.5ч (требуется 10M в сейфе)"
        }
        
        info += f"\n💼 Зарплата уровня {club_data['level']}: {salary_info.get(club_data['level'], 'Не установлена')}"
        
        return info

bot_data = CasinoBot()

def help_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    help_text = """
🤖 **КОМАНДЫ БОТА** 🤖

🎮 **Игры:**
/play [ставка] [игра] - Сыграть в игру
/wheel - Колесо удачи (100 PC)

💰 **Экономика:**
/balance - Ваш баланс
/daily - Ежедневная награда
/transfer [@username/ID] [сумма] - Перевести деньги

🏦 **Банк:**
/regbank [название] - Создать банковский счет
/bank - Управление счетами
/infobank - Информация о счетах

👥 **Друзья:**
/addfriend [ID] - Добавить друга
/messagefriend [имя] [сообщение] - Написать другу

🏢 **Клубы:**
/createclub [название] - Создать клуб
/club - Информация о клубе
/crank [ID] [ранг] - Выдать ранг участнику
/cchat [сообщение] - Написать в чат клуба
/csafe [сумма] [сообщение] - Положить в сейф клуба
/ccsafe [сумма] - Взять из сейфа клуба
/cbuylevel [уровень] - Купить уровень клуба
/cadd [ID/@username] - Добавить участника в клуб
/cleave - Выйти из клуба

📊 **Информация:**
/stats - Ваша статистика
/leaderboard - Таблица лидеров
/shop - Магазин привилегий

🎁 **Дополнительно:**
/promo [код] - Активировать промокод
/repriv [привилегия] - Сменить привилегию
/author - Информация об авторе
/q [сообщение] - Ответить администрации

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
    elif data.startswith("friend_accept_"):
        from_user_id = int(data.split("_")[2])
        to_user_id = query.from_user.id
        
        if bot_data.accept_friend_request(to_user_id, from_user_id, context):
            query.edit_message_text("✅ Запрос в друзья принят!")
        else:
            query.edit_message_text("❌ Запрос не найден")
    
    elif data.startswith("friend_decline_"):
        from_user_id = int(data.split("_")[2])
        to_user_id = query.from_user.id
        
        if to_user_id in bot_data.friends_requests and from_user_id in bot_data.friends_requests[to_user_id]:
            del bot_data.friends_requests[to_user_id][from_user_id]
            bot_data.save_data()
            
            try:
                context.bot.send_message(
                    chat_id=from_user_id,
                    text=f"❌ Пользователь @{bot_data.users[to_user_id]['username']} отклонил ваш запрос в друзья."
                )
            except Exception:
                pass
            
            query.edit_message_text("❌ Запрос в друзья отклонен")
    
    elif data.startswith("club_accept_"):
        club_name = data.split("_")[2]
        user_id = query.from_user.id
        
        success, message = bot_data.accept_club_invite(user_id, club_name, context)
        if success:
            query.edit_message_text(f"✅ Вы присоединились к клубу '{club_name}'!")
        else:
            query.edit_message_text("❌ Приглашение не найдено или устарело")
    
    elif data.startswith("club_decline_"):
        club_name = data.split("_")[2]
        user_id = query.from_user.id
        
        if club_name in bot_data.club_join_requests and user_id in bot_data.club_join_requests[club_name]:
            from_user_id = bot_data.club_join_requests[club_name][user_id]["from_user"]
            del bot_data.club_join_requests[club_name][user_id]
            bot_data.save_data()
            
            try:
                context.bot.send_message(
                    chat_id=from_user_id,
                    text=f"❌ Пользователь @{bot_data.users[user_id]['username']} отклонил ваше приглашение в клуб '{club_name}'."
                )
            except Exception:
                pass
            
            query.edit_message_text(f"❌ Вы отклонили приглашение в клуб '{club_name}'")

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
        "/givepc [ID] [количество] - выдать PlayCoin",
        "",
        "🏢 КЛУБЫ (Создатель):",
        "/infoclub [название] - информация о клубе",
        "/testmode_user - войти в тестовый режим",
        "/untest - выйти из тестового режима"
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
            except Exception:
                pass
    
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
        except Exception:
            failed_count += 1
    
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
            "• temp_privilege gold 24 - временная привилегия на 24 часа\n"
            "• donate TITAN - донат\n\n"
            "Примеры:\n"
            "/createpromo TEST1 cash 1000\n"
            "/createpromo TEST2 multiplier 2 1\n"
            "/createpromo TEST3 privilege gold\n"
            "/createpromo TEST4 temp_privilege gold 24\n"
            "/createpromo TEST5 donate TITAN"
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
    
    elif reward_type == "temp_privilege":
        if len(context.args) < 4:
            update.message.reply_text("Укажите привилегию и длительность: /createpromo [код] temp_privilege [привилегия] [часы]")
            return
        value = context.args[2].lower()
        duration = int(context.args[3])
        if value not in bot_data.privileges:
            update.message.reply_text("❌ Неверная привилегия. Доступно: bronze, silver, gold, platinum")
            return
        bot_data.create_promo_code(code, "temp_privilege", value, duration)
        update.message.reply_text(f"✅ Промокод создан: {code}\nНаграда: временная привилегия {bot_data.privileges[value]['title']} на {duration} часов")
    
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
        update.message.reply_text("❌ Неверный тип награды. Доступно: cash, multiplier, privilege, temp_privilege, donate")

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

def addfriend(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
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
    
    bot_data.add_friend_request(user_id, target_id)
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Принять", callback_data=f"friend_accept_{user_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"friend_decline_{user_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        from_username = bot_data.users[user_id]["username"] or str(user_id)
        context.bot.send_message(
            chat_id=target_id,
            text=f"👥 Запрос в друзья\nОт: @{from_username} (ID: {user_id})\n\nХотите принять?",
            reply_markup=reply_markup
        )
        update.message.reply_text("✅ Запрос в друзья отправлен!")
    except Exception:
        update.message.reply_text("❌ Не удалось отправить запрос")

def messagefriend(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
    if len(context.args) < 2:
        update.message.reply_text("Использование: /messagefriend [имя друга] [сообщение]")
        return
    
    friend_name = context.args[0]
    message = ' '.join(context.args[1:])
    
    result = bot_data.send_message_to_friend(user_id, friend_name, message)
    
    if isinstance(result, int):
        try:
            context.bot.send_message(
                chat_id=result,
                text=f"💌 Сообщение от друга @{update.effective_user.username}:\n\n{message}"
            )
            update.message.reply_text("✅ Сообщение отправлено другу!")
        except Exception:
            update.message.reply_text("❌ Не удалось отправить сообщение")
    else:
        update.message.reply_text(result)

def createclub(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
    if not context.args:
        update.message.reply_text(
            "🏢 Создание клуба\n\n"
            "Использование: /createclub [название клуба]\n\n"
            "💡 Стоимость: 200 PlayCoin или 5,000,000 монет"
        )
        return
    
    club_name = ' '.join(context.args)
    result = bot_data.create_club(user_id, club_name)
    update.message.reply_text(result)

def club(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    user = bot_data.users[user_id]
    
    if "club" not in user or not user["club"]:
        update.message.reply_text("❌ Вы не состоите в клубе")
        return
    
    club_name = user["club"]
    club_data = bot_data.clubs[club_name]
    club_ranks = bot_data.club_ranks[club_name]
    
    creator_username = bot_data.users[club_data["creator"]]["username"] or "Неизвестно"
    member_count = len(club_data["members"])
    
    response = f"🏢 **КЛУБ: {club_name}**\n\n"
    response += f"👑 Создатель: @{creator_username}\n"
    response += f"👥 Участников: {member_count}\n"
    response += f"💰 Сейф: {club_data['safe_balance']} монет\n"
    response += f"📊 Уровень: {club_data['level']}\n"
    response += f"🎯 Ваш ранг: {club_ranks[user['club_rank']]}\n"
    
    if user_id == club_data["creator"]:
        response += f"\n💡 Зарплаты:\n"
        response += f"• Уровень 1 (2M): 20,000 каждые 2.5ч\n"
        response += f"• Уровень 2 (5M): 50,000 каждые 2.5ч\n"
        response += f"• Уровень 3 (10M): 250,000 каждые 2.5ч\n"
        response += f"\n⚙️ Команды создателя: /crank, /ccsafe, /cbuylevel"
    
    update.message.reply_text(response, parse_mode='Markdown')

def crank(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
    if len(context.args) != 2:
        update.message.reply_text(
            "🎖️ Выдача ранга участнику клуба\n\n"
            "Использование: /crank [ID участника] [ранг 1-5]\n\n"
            "💡 Только создатель клуба может выдавать ранги"
        )
        return
    
    try:
        target_id = int(context.args[0])
        rank = int(context.args[1])
    except ValueError:
        update.message.reply_text("❌ ID и ранг должны быть числами")
        return
    
    result = bot_data.set_club_rank(user_id, target_id, rank)
    update.message.reply_text(result)

def cchat(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
    if not context.args:
        update.message.reply_text("Использование: /cchat [сообщение]")
        return
    
    message = ' '.join(context.args)
    result = bot_data.send_club_message(user_id, message, context)
    update.message.reply_text(result)

def csafe(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
    if len(context.args) < 1:
        update.message.reply_text(
            "💰 Положить деньги в сейф клуба\n\n"
            "Использование: /csafe [сумма] (сообщение)\n\n"
            "💡 Деньги списываются с основного баланса"
        )
        return
    
    try:
        amount = int(context.args[0])
        message = ' '.join(context.args[1:]) if len(context.args) > 1 else ""
    except ValueError:
        update.message.reply_text("❌ Сумма должна быть числом")
        return
    
    result = bot_data.deposit_to_club_safe(user_id, amount, message)
    update.message.reply_text(result)

def ccsafe(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
    if len(context.args) != 1:
        update.message.reply_text(
            "💰 Взять деньги из сейфа клуба\n\n"
            "Использование: /ccsafe [сумма]\n\n"
            "💡 Только создатель клуба может брать деньги"
        )
        return
    
    try:
        amount = int(context.args[0])
    except ValueError:
        update.message.reply_text("❌ Сумма должна быть числом")
        return
    
    result = bot_data.withdraw_from_club_safe(user_id, amount)
    update.message.reply_text(result)

def cbuylevel(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
    if len(context.args) != 1:
        update.message.reply_text(
            "📈 Купить уровень клуба\n\n"
            "Использование: /cbuylevel [номер уровня]\n\n"
            "💡 Уровни: 1 (2M), 2 (5M), 3 (10M)\n"
            "💡 Только создатель клуба может покупать уровни"
        )
        return
    
    try:
        level = int(context.args[0])
    except ValueError:
        update.message.reply_text("❌ Уровень должен быть числом")
        return
    
    result = bot_data.buy_club_level(user_id, level)
    update.message.reply_text(result)

def cadd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
    if not context.args:
        update.message.reply_text(
            "👥 Добавить участника в клуб\n\n"
            "Использование: /cadd [ID или @username]\n\n"
            "💡 Только создатель клуба может добавлять участников"
        )
        return
    
    target_input = context.args[0]
    result = bot_data.add_member_to_club(user_id, target_input)
    
    if isinstance(result, int):
        user = bot_data.users[user_id]
        club_name = user["club"]
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Вступить", callback_data=f"club_accept_{club_name}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"club_decline_{club_name}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            from_username = bot_data.users[user_id]["username"] or str(user_id)
            context.bot.send_message(
                chat_id=result,
                text=f"🏢 Приглашение в клуб\nОт: @{from_username} (ID: {user_id})\nКлуб: {club_name}\n\nХотите присоединиться?",
                reply_markup=reply_markup
            )
            update.message.reply_text("✅ Приглашение отправлено!")
        except Exception:
            update.message.reply_text("❌ Не удалось отправить приглашение")
    else:
        update.message.reply_text(result)

def cleave(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    bot_data.users[user_id]["last_activity"] = time.time()
    bot_data.save_data()
    
    if not context.args:
        update.message.reply_text(
            "🚪 Выйти из клуба\n\n"
            "Использование: /cleave да\n\n"
            "⚠️ Если вы создатель, клуб будет распущен!"
        )
        return
    
    confirmation = context.args[0].lower()
    if confirmation != "да":
        update.message.reply_text("❌ Для выхода из клуба напишите: /cleave да")
        return
    
    result = bot_data.leave_club(user_id)
    update.message.reply_text(result)

def infoclub(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_creator_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if not context.args:
        update.message.reply_text("Использование: /infoclub [название клуба]")
        return
    
    club_name = ' '.join(context.args)
    result = bot_data.get_club_info(club_name)
    update.message.reply_text(result, parse_mode='Markdown')

def testmode_user(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_creator_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    test_user_id = user_id + 1000000
    bot_data.init_user(test_user_id, "test_user")
    bot_data.users[test_user_id]["balance"] = 10000
    bot_data.users[test_user_id]["play_coins"] = 100
    
    bot_data.save_data()
    
    update.message.reply_text(
        f"🔧 Тестовый режим активирован!\n"
        f"🆔 Ваш тестовый ID: {test_user_id}\n"
        f"💡 Используйте этот ID для тестирования как обычный пользователь"
    )

def untest(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not bot_data.is_creator_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    test_user_id = user_id + 1000000
    if test_user_id in bot_data.users:
        del bot_data.users[test_user_id]
        bot_data.save_data()
    
    update.message.reply_text("✅ Тестовый режим деактивирован!")

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

def main():
    if not TOKEN:
        logger.error("❌ Токен не найден! Установите переменную TELEGRAM_TOKEN")
        return
    
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    
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
    
    dispatcher.add_handler(CommandHandler("help", help_cmd))
    dispatcher.add_handler(CommandHandler("balance", balance))
    dispatcher.add_handler(CommandHandler("daily", daily))
    dispatcher.add_handler(CommandHandler("transfer", transfer))
    dispatcher.add_handler(CommandHandler("regbank", regbank))
    dispatcher.add_handler(CommandHandler("bank", bank))
    dispatcher.add_handler(CommandHandler("infobank", infobank))
    
    dispatcher.add_handler(CommandHandler("register", register))
    dispatcher.add_handler(CommandHandler("panel", panel))
    dispatcher.add_handler(CommandHandler("creatorcmd", creatorcmd))
    
    dispatcher.add_handler(CommandHandler("backup", backup))
    dispatcher.add_handler(CommandHandler("globalstats", globalstats))
    dispatcher.add_handler(CommandHandler("givepc", givepc))
    dispatcher.add_handler(CommandHandler("infoclub", infoclub))
    dispatcher.add_handler(CommandHandler("testmode_user", testmode_user))
    dispatcher.add_handler(CommandHandler("untest", untest))
    
    dispatcher.add_handler(CommandHandler("setdonate", setdonate))
    dispatcher.add_handler(CommandHandler("message", message_cmd))
    dispatcher.add_handler(CommandHandler("givecash", givecash))
    dispatcher.add_handler(CommandHandler("givedonate", givedonate))
