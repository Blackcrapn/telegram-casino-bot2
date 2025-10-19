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
        
        # Новые поля для социальных функций
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
        
        # Настройка аварийного сохранения
        self.setup_emergency_save()

    def setup_emergency_save(self):
        """Настройка надежного аварийного сохранения"""
        def emergency_handler():
            try:
                logger.info("🔄 Emergency save: Сохранение данных...")
                self.save_data()
                self.save_social_data()
                logger.info("✅ Emergency save: Данные успешно сохранены")
            except Exception as e:
                logger.error(f"❌ Emergency save failed: {e}")
        
        def signal_handler(signum, frame):
            logger.info(f"📦 Получен сигнал {signum}, сохраняем данные...")
            emergency_handler()
            exit(0)
        
        # Регистрируем обработчики
        atexit.register(emergency_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        logger.info("🛡️ Надежная система emergency save активирована")

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
                self.last_reply_time = {int(k): v for k, v in self.last_reply_time.items()}
                
                logger.info("💾 Данные успешно загружены")
            else:
                logger.info("📝 Файл данных не найден, создаем новую базу")
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке данных: {e}")

    def save_social_data(self):
        """Сохранение социальных данных"""
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
            logger.info("💾 Социальные данные сохранены")
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении социальных данных: {e}")

    def load_social_data(self):
        """Загрузка социальных данных"""
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
                
                # Конвертация ключей в int
                self.friends_requests = {int(k): {int(k2): v2 for k2, v2 in v.items()} for k, v in self.friends_requests.items()}
                self.friends = {int(k): v for k, v in self.friends.items()}
                self.user_clubs = {int(k): v for k, v in self.user_clubs.items()}
                self.test_mode_users = {int(k): v for k, v in self.test_mode_users.items()}
                self.pending_withdrawals = {int(k): v for k, v in self.pending_withdrawals.items()}
                
                logger.info("💾 Социальные данные загружены")
            else:
                logger.info("📝 Файл социальных данных не найден, создаем новую базу")
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке социальных данных: {e}")

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

    # Новые методы для социальных функций
    def add_friend_request(self, from_user_id: int, to_user_id: int):
        """Добавление запроса в друзья"""
        if to_user_id not in self.friends_requests:
            self.friends_requests[to_user_id] = {}
        
        self.friends_requests[to_user_id][from_user_id] = time.time()
        self.save_social_data()

    def accept_friend_request(self, user_id: int, from_user_id: int):
        """Принятие запроса в друзья"""
        if user_id not in self.friends:
            self.friends[user_id] = []
        if from_user_id not in self.friends:
            self.friends[from_user_id] = []
        
        if from_user_id not in self.friends[user_id]:
            self.friends[user_id].append(from_user_id)
        if user_id not in self.friends[from_user_id]:
            self.friends[from_user_id].append(user_id)
        
        # Удаляем запрос
        if user_id in self.friends_requests and from_user_id in self.friends_requests[user_id]:
            del self.friends_requests[user_id][from_user_id]
        
        self.save_social_data()

    def reject_friend_request(self, user_id: int, from_user_id: int):
        """Отклонение запроса в друзья"""
        if user_id in self.friends_requests and from_user_id in self.friends_requests[user_id]:
            del self.friends_requests[user_id][from_user_id]
            self.save_social_data()

    def get_friend_by_name(self, user_id: int, friend_name: str) -> Optional[int]:
        """Поиск друга по имени"""
        if user_id not in self.friends:
            return None
        
        for friend_id in self.friends[user_id]:
            friend_data = self.users.get(friend_id, {})
            if friend_data.get("username", "").lower() == friend_name.lower():
                return friend_id
        return None

    def create_club(self, user_id: int, club_name: str, cost_type: str) -> str:
        """Создание клуба"""
        if club_name in self.clubs:
            return "❌ Клуб с таким названием уже существует"
        
        user = self.users[user_id]
        
        # Проверка стоимости
        if cost_type == "pc":
            if user["play_coins"] < 200:
                return "❌ Недостаточно PlayCoin (нужно 200)"
            user["play_coins"] -= 200
        else:  # coins
            if user["balance"] < 5000000:
                return "❌ Недостаточно монет (нужно 5,000,000)"
            user["balance"] -= 5000000
        
        # Создание клуба
        self.clubs[club_name] = {
            "owner": user_id,
            "members": {user_id: {"rank": 6, "joined_at": time.time()}},  # 6 - создатель
            "ranks": ["Новичок", "Участник", "Активный", "Офицер", "Вице-лидер"],
            "created_at": time.time(),
            "description": ""
        }
        
        # Добавление в пользовательские клубы
        if user_id not in self.user_clubs:
            self.user_clubs[user_id] = []
        self.user_clubs[user_id].append(club_name)
        
        # Инициализация чата и сейфа
        self.club_chats[club_name] = []
        self.club_safes[club_name] = {"balance": 0, "transactions": []}
        
        self.save_data()
        self.save_social_data()
        return f"✅ Клуб '{club_name}' успешно создан!"

    def add_club_members(self, user_id: int, club_name: str, usernames: List[str]) -> str:
        """Добавление участников в клуб"""
        if club_name not in self.clubs:
            return "❌ Клуб не найден"
        
        club = self.clubs[club_name]
        if club["owner"] != user_id:
            return "❌ Только создатель клуба может добавлять участников"
        
        added_count = 0
        for username in usernames:
            username = username.replace('@', '')
            found_users = self.search_user_by_username(username)
            if found_users:
                target_id, target_data = found_users[0]
                if target_id not in club["members"]:
                    club["members"][target_id] = {"rank": 1, "joined_at": time.time()}
                    
                    if target_id not in self.user_clubs:
                        self.user_clubs[target_id] = []
                    if club_name not in self.user_clubs[target_id]:
                        self.user_clubs[target_id].append(club_name)
                    
                    added_count += 1
        
        self.save_social_data()
        return f"✅ Добавлено {added_count} участников в клуб"

    def change_member_rank(self, user_id: int, club_name: str, target_id: int, new_rank: int) -> str:
        """Изменение ранга участника"""
        if club_name not in self.clubs:
            return "❌ Клуб не найден"
        
        club = self.clubs[club_name]
        if club["owner"] != user_id:
            return "❌ Только создатель клуба может изменять ранги"
        
        if target_id not in club["members"]:
            return "❌ Участник не найден в клубе"
        
        if new_rank < 1 or new_rank > 5:
            return "❌ Ранг должен быть от 1 до 5"
        
        club["members"][target_id]["rank"] = new_rank
        self.save_social_data()
        rank_name = club["ranks"][new_rank - 1] if new_rank <= len(club["ranks"]) else f"Ранг {new_rank}"
        return f"✅ Ранг участника изменен на: {rank_name}"

    def update_club_ranks(self, user_id: int, club_name: str, ranks: List[str]) -> str:
        """Обновление названий рангов"""
        if club_name not in self.clubs:
            return "❌ Клуб не найден"
        
        club = self.clubs[club_name]
        if club["owner"] != user_id:
            return "❌ Только создатель клуба может изменять ранги"
        
        if len(ranks) != 5:
            return "❌ Должно быть ровно 5 названий рангов"
        
        club["ranks"] = ranks
        self.save_social_data()
        return "✅ Названия рангов обновлены!"

    def send_club_message(self, user_id: int, club_name: str, message: str, context: CallbackContext = None):
        """Отправка сообщения в чат клуба всем участникам"""
        if club_name not in self.clubs or user_id not in self.clubs[club_name]["members"]:
            return "❌ Вы не состоите в этом клубе"
        
        user_data = self.users[user_id]
        username = user_data.get("username", f"ID:{user_id}")
        
        # Сохраняем сообщение в истории
        message_data = {
            "user_id": user_id,
            "username": username,
            "message": message,
            "timestamp": time.time()
        }
        
        self.club_chats[club_name].append(message_data)
        
        # Ограничиваем историю сообщений
        if len(self.club_chats[club_name]) > 100:
            self.club_chats[club_name] = self.club_chats[club_name][-100:]
        
        # Рассылаем сообщение всем участникам клуба
        club = self.clubs[club_name]
        sent_count = 0
        
        for member_id in club["members"]:
            try:
                # Формируем отображаемое имя отправителя
                sender_display = f"{user_id}"
                if username and username != f"ID:{user_id}":
                    sender_display += f" (@{username})"
                
                # Отправляем сообщение участнику
                if context:
                    context.bot.send_message(
                        chat_id=member_id,
                        text=f"🏰 Клуб: {club_name}\n👤 Отправитель: {sender_display}\n💬 Сообщение: {message}"
                    )
                    sent_count += 1
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение участнику {member_id}: {e}")
        
        self.save_social_data()
        return f"✅ Сообщение отправлено в чат клуба '{club_name}' (доставлено {sent_count} участникам)"

    def deposit_to_club_safe(self, user_id: int, club_name: str, amount: int, note: str = "") -> str:
        """Пополнение сейфа клуба"""
        if club_name not in self.clubs or user_id not in self.clubs[club_name]["members"]:
            return "❌ Вы не состоите в этом клубе"
        
        user = self.users[user_id]
        if user["balance"] < amount:
            return "❌ Недостаточно средств на балансе"
        
        if amount <= 0:
            return "❌ Сумма должна быть положительной"
        
        # Снимаем деньги с пользователя
        user["balance"] -= amount
        
        # Пополняем сейф клуба
        if club_name not in self.club_safes:
            self.club_safes[club_name] = {"balance": 0, "transactions": []}
        
        self.club_safes[club_name]["balance"] += amount
        
        # Добавляем запись о транзакции
        transaction = {
            "user_id": user_id,
            "username": user["username"],
            "amount": amount,
            "note": note,
            "timestamp": time.time(),
            "type": "deposit"
        }
        self.club_safes[club_name]["transactions"].append(transaction)
        
        self.save_data()
        self.save_social_data()
        return f"✅ В сейф клуба '{club_name}' внесено {amount}💰\n💳 Ваш баланс: {user['balance']}💰"

    def request_safe_withdrawal(self, user_id: int, club_name: str, amount: int) -> str:
        """Запрос на снятие денег из сейфа клуба"""
        if club_name not in self.clubs:
            return "❌ Клуб не найден"
        
        club = self.clubs[club_name]
        if club["owner"] != user_id:
            return "❌ Только создатель клуба может снимать деньги из сейфа"
        
        if club_name not in self.club_safes:
            return "❌ В сейфе клуба нет денег"
        
        safe_balance = self.club_safes[club_name]["balance"]
        if amount <= 0:
            return "❌ Сумма должна быть положительной"
        
        if safe_balance < amount:
            return f"❌ В сейфе недостаточно средств. Доступно: {safe_balance}"
        
        # Сохраняем запрос на снятие
        self.pending_withdrawals[user_id] = {
            "club_name": club_name,
            "amount": amount,
            "timestamp": time.time()
        }
        
        self.save_social_data()
        return "waiting_confirmation"

    def process_safe_withdrawal(self, user_id: int, confirm: bool) -> str:
        """Обработка подтверждения снятия денег из сейфа"""
        if user_id not in self.pending_withdrawals:
            return "❌ Нет активных запросов на снятие"
        
        withdrawal = self.pending_withdrawals[user_id]
        club_name = withdrawal["club_name"]
        amount = withdrawal["amount"]
        
        if not confirm:
            del self.pending_withdrawals[user_id]
            self.save_social_data()
            return "❌ Снятие отменено"
        
        # Проверяем, что условия все еще актуальны
        if club_name not in self.clubs or self.clubs[club_name]["owner"] != user_id:
            del self.pending_withdrawals[user_id]
            self.save_social_data()
            return "❌ Вы больше не являетесь создателем клуба"
        
        if club_name not in self.club_safes or self.club_safes[club_name]["balance"] < amount:
            del self.pending_withdrawals[user_id]
            self.save_social_data()
            return "❌ В сейфе недостаточно средств"
        
        # Снимаем деньги
        self.club_safes[club_name]["balance"] -= amount
        self.users[user_id]["balance"] += amount
        
        # Добавляем запись о транзакции
        transaction = {
            "user_id": user_id,
            "username": self.users[user_id]["username"],
            "amount": amount,
            "note": "Снятие из сейфа клуба",
            "timestamp": time.time(),
            "type": "withdraw"
        }
        self.club_safes[club_name]["transactions"].append(transaction)
        
        del self.pending_withdrawals[user_id]
        self.save_data()
        self.save_social_data()
        
        return f"✅ Успешно снято {amount}💰 из сейфа клуба '{club_name}'\n💳 Ваш баланс: {self.users[user_id]['balance']}💰"

    def enter_test_mode(self, creator_id: int) -> str:
        """Вход в тестовый режим для создателя"""
        if not self.is_creator(creator_id):
            return "❌ Эта команда только для создателя"
        
        # Создаем тестового пользователя
        test_user_id = creator_id + 1000000  # Уникальный ID для теста
        
        self.test_mode_users[creator_id] = {
            "test_user_id": test_user_id,
            "original_data": self.users[creator_id].copy(),
            "entered_at": time.time()
        }
        
        # Создаем тестового пользователя с обычными правами
        self.init_user(test_user_id, f"test_{self.users[creator_id]['username']}")
        self.users[test_user_id]["balance"] = 10000
        self.users[test_user_id]["play_coins"] = 100
        self.users[test_user_id]["is_admin"] = False
        
        self.save_social_data()
        return f"✅ Тестовый режим активирован! Ваш тестовый ID: {test_user_id}\nТеперь вы обычный пользователь и можете участвовать в лидерборде."

    def exit_test_mode(self, creator_id: int) -> str:
        """Выход из тестового режима"""
        if creator_id not in self.test_mode_users:
            return "❌ Вы не в тестовом режиме"
        
        test_data = self.test_mode_users[creator_id]
        test_user_id = test_data["test_user_id"]
        
        # Удаляем тестового пользователя
        if test_user_id in self.users:
            del self.users[test_user_id]
        
        del self.test_mode_users[creator_id]
        self.save_social_data()
        return "✅ Тестовый режим деактивирован. Вы снова создатель бота."

    def get_club_info(self, club_name: str) -> Dict:
        """Получение информации о клубе"""
        if club_name not in self.clubs:
            return {}
        
        club = self.clubs[club_name].copy()
        safe_balance = self.club_safes.get(club_name, {}).get("balance", 0)
        club["safe_balance"] = safe_balance
        club["members_count"] = len(club["members"])
        
        return club

    def search_user_by_username(self, username: str) -> List[Tuple[int, Dict]]:
        found_users = []
        username = username.lower().replace('@', '')
        
        for user_id, user_data in self.users.items():
            if user_data["username"] and user_data["username"].lower() == username:
                found_users.append((user_id, user_data))
                
        return found_users

    # Остальные существующие методы класса CasinoBot остаются без изменений
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
                    "exclusive_donate": None,
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

# ==================== НОВЫЕ КОМАНДЫ ====================

def addfriend(update: Update, context: CallbackContext):
    """Добавить в друзья"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    if not context.args:
        update.message.reply_text(
            "👥 Добавить в друзья\n\n"
            "Использование: /addfriend [ID пользователя]\n\n"
            "Пример: /addfriend 123456789"
        )
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
        update.message.reply_text("❌ Не удалось отправить запрос. Пользователь, возможно, не начинал диалог с ботом.")

def messagefriend(update: Update, context: CallbackContext):
    """Написать сообщение другу"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    if len(context.args) < 2:
        update.message.reply_text(
            "💬 Написать сообщение другу\n\n"
            "Использование: /messagefriend [имя_друга] [сообщение]\n\n"
            "Пример: /messagefriend username Привет, как дела?"
        )
        return
    
    friend_name = context.args[0]
    message = ' '.join(context.args[1:])
    
    bot_data.init_user(user_id, update.effective_user.username)
    
    # Ищем друга по имени
    friend_id = bot_data.get_friend_by_name(user_id, friend_name)
    if not friend_id:
        update.message.reply_text("❌ Друг с таким именем не найден")
        return
    
    try:
        # Отправляем сообщение другу
        sender_username = bot_data.users[user_id]["username"] or f"ID:{user_id}"
        context.bot.send_message(
            chat_id=friend_id,
            text=f"💬 Сообщение от друга @{sender_username}:\n\n{message}"
        )
        update.message.reply_text("✅ Сообщение отправлено другу!")
    except Exception as e:
        update.message.reply_text("❌ Не удалось отправить сообщение. Друг, возможно, заблокировал бота.")

def createclub(update: Update, context: CallbackContext):
    """Создать клуб"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    if len(context.args) < 1:
        update.message.reply_text(
            "🏰 Создать клуб\n\n"
            "Использование: /createclub [название] (участники через @)\n\n"
            "Стоимость: 200 PlayCoin или 5,000,000 монет\n\n"
            "Примеры:\n"
            "/createclub MyClub\n"
            "/createclub BestClub @user1 @user2\n\n"
            "После создания используйте команды:\n"
            "/club - информация о клубе\n"
            "/cchat - написать в чат клуба"
        )
        return
    
    club_name = context.args[0]
    members = context.args[1:] if len(context.args) > 1 else []
    
    bot_data.init_user(user_id, update.effective_user.username)
    
    # Проверяем, может ли пользователь создать клуб
    user = bot_data.users[user_id]
    can_create_pc = user["play_coins"] >= 200
    can_create_coins = user["balance"] >= 5000000
    
    if not can_create_pc and not can_create_coins:
        update.message.reply_text(
            "❌ Недостаточно средств для создания клуба\n\n"
            "Нужно: 200 PlayCoin ИЛИ 5,000,000 монет"
        )
        return
    
    # Создаем клавиатуру для выбора способа оплаты
    keyboard = []
    if can_create_pc:
        keyboard.append([InlineKeyboardButton("💎 200 PlayCoin", callback_data=f"createclub_pc_{club_name}")])
    if can_create_coins:
        keyboard.append([InlineKeyboardButton("💰 5,000,000 монет", callback_data=f"createclub_coins_{club_name}")])
    
    if not keyboard:
        update.message.reply_text("❌ Недостаточно средств")
        return
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    members_text = ""
    if members:
        members_text = f"\n👥 Участники: {', '.join(members)}"
    
    update.message.reply_text(
        f"🏰 Создание клуба: {club_name}\n\n"
        f"Выберите способ оплаты:{members_text}",
        reply_markup=reply_markup
    )

def club(update: Update, context: CallbackContext):
    """Информация о клубе"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    
    # Получаем клубы пользователя
    user_clubs = bot_data.user_clubs.get(user_id, [])
    
    if not user_clubs:
        update.message.reply_text(
            "🏰 Вы не состоите ни в одном клубе\n\n"
            "Создайте клуб: /createclub [название]\n"
            "Или попросите друга добавить вас в клуб"
        )
        return
    
    # Если пользователь в одном клубе - показываем его информацию
    if len(user_clubs) == 1:
        club_name = user_clubs[0]
        club_info = bot_data.get_club_info(club_name)
        
        if not club_info:
            update.message.reply_text("❌ Информация о клубе не найдена")
            return
        
        # Формируем информацию о клубе
        owner_username = bot_data.users[club_info["owner"]]["username"] if club_info["owner"] in bot_data.users else "Неизвестно"
        members_text = ""
        
        for member_id, member_data in club_info["members"].items():
            member_username = bot_data.users[member_id]["username"] if member_id in bot_data.users else f"ID:{member_id}"
            rank = member_data["rank"]
            rank_name = club_info["ranks"][rank-1] if rank <= 5 else "👑 Создатель"
            members_text += f"• {member_username} - {rank_name}\n"
        
        response = (
            f"🏰 Клуб: {club_name}\n\n"
            f"👑 Создатель: @{owner_username}\n"
            f"👥 Участников: {club_info['members_count']}\n"
            f"💰 Сейф: {club_info['safe_balance']} монет\n"
            f"📅 Создан: {time.strftime('%Y-%m-%d', time.localtime(club_info['created_at']))}\n\n"
            f"👥 Участники:\n{members_text}\n"
            f"💬 Чат клуба: /cchat [сообщение]\n"
            f"🏦 Сейф: /csafe [сумма] [сообщение]\n"
            f"💸 Снять из сейфа: /csafewithdraw [сумма]"
        )
        
        update.message.reply_text(response)
    else:
        # Если несколько клубов - показываем список
        clubs_text = "\n".join([f"• {club}" for club in user_clubs])
        update.message.reply_text(
            f"🏰 Ваши клубы:\n\n{clubs_text}\n\n"
            f"Для просмотра информации о конкретном клубе используйте: /club [название]"
        )

def crank(update: Update, context: CallbackContext):
    """Изменить ранг участника клуба"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    if len(context.args) != 2:
        update.message.reply_text(
            "📊 Изменить ранг участника клуба\n\n"
            "Использование: /crank [ID участника] [новый ранг (1-5)]\n\n"
            "Пример: /crank 123456789 3\n\n"
            "💡 Доступно только создателю клуба"
        )
        return
    
    try:
        target_id = int(context.args[0])
        new_rank = int(context.args[1])
    except ValueError:
        update.message.reply_text("❌ ID и ранг должны быть числами")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    
    # Находим клуб, где пользователь является создателем
    user_clubs = bot_data.user_clubs.get(user_id, [])
    target_club = None
    
    for club_name in user_clubs:
        club = bot_data.clubs.get(club_name, {})
        if club.get("owner") == user_id:
            target_club = club_name
            break
    
    if not target_club:
        update.message.reply_text("❌ Вы не являетесь создателем ни одного клуба")
        return
    
    result = bot_data.change_member_rank(user_id, target_club, target_id, new_rank)
    update.message.reply_text(result)

def cchat(update: Update, context: CallbackContext):
    """Написать сообщение в чат клуба"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    if not context.args:
        update.message.reply_text(
            "💬 Чат клуба\n\n"
            "Использование: /cchat [сообщение]\n\n"
            "Пример: /cchat Привет всем!"
        )
        return
    
    message = ' '.join(context.args)
    bot_data.init_user(user_id, update.effective_user.username)
    
    # Находим клуб пользователя (берем первый, если несколько)
    user_clubs = bot_data.user_clubs.get(user_id, [])
    if not user_clubs:
        update.message.reply_text("❌ Вы не состоите ни в одном клубе")
        return
    
    club_name = user_clubs[0]  # Берем первый клуб
    result = bot_data.send_club_message(user_id, club_name, message, context)
    update.message.reply_text(result)

def ccmd(update: Update, context: CallbackContext):
    """Изменить названия рангов клуба"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    if len(context.args) != 5:
        update.message.reply_text(
            "⚙️ Изменить названия рангов клуба\n\n"
            "Использование: /ccmd [ранг1] [ранг2] [ранг3] [ранг4] [ранг5]\n\n"
            "Пример: /ccmd Новичок Участник Активный Офицер Вице-лидер\n\n"
            "💡 Доступно только создателю клуба"
        )
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    
    # Находим клуб, где пользователь является создателем
    user_clubs = bot_data.user_clubs.get(user_id, [])
    target_club = None
    
    for club_name in user_clubs:
        club = bot_data.clubs.get(club_name, {})
        if club.get("owner") == user_id:
            target_club = club_name
            break
    
    if not target_club:
        update.message.reply_text("❌ Вы не являетесь создателем ни одного клуба")
        return
    
    result = bot_data.update_club_ranks(user_id, target_club, context.args)
    update.message.reply_text(result)

def csafe(update: Update, context: CallbackContext):
    """Положить деньги в сейф клуба"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    if len(context.args) < 2:
        update.message.reply_text(
            "🏦 Сейф клуба\n\n"
            "Использование: /csafe [сумма] [сообщение]\n\n"
            "Пример: /csafe 1000 На развитие клуба\n\n"
            "💡 Деньги снимаются с вашего основного баланса"
        )
        return
    
    try:
        amount = int(context.args[0])
        note = ' '.join(context.args[1:])
    except ValueError:
        update.message.reply_text("❌ Сумма должна быть числом")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    
    # Находим клуб пользователя (берем первый, если несколько)
    user_clubs = bot_data.user_clubs.get(user_id, [])
    if not user_clubs:
        update.message.reply_text("❌ Вы не состоите ни в одном клубе")
        return
    
    club_name = user_clubs[0]  # Берем первый клуб
    result = bot_data.deposit_to_club_safe(user_id, club_name, amount, note)
    update.message.reply_text(result)

def csafewithdraw(update: Update, context: CallbackContext):
    """Забрать деньги из сейфа клуба"""
    user_id = update.effective_user.id
    
    if bot_data.is_banned(user_id):
        update.message.reply_text("❌ Вы забанены.")
        return
    
    if len(context.args) != 1:
        update.message.reply_text(
            "💸 Снять деньги из сейфа клуба\n\n"
            "Использование: /csafewithdraw [сумма]\n\n"
            "Пример: /csafewithdraw 1000\n\n"
            "💡 Доступно только создателю клуба"
        )
        return
    
    try:
        amount = int(context.args[0])
    except ValueError:
        update.message.reply_text("❌ Сумма должна быть числом")
        return
    
    bot_data.init_user(user_id, update.effective_user.username)
    
    # Находим клуб, где пользователь является создателем
    user_clubs = bot_data.user_clubs.get(user_id, [])
    target_club = None
    
    for club_name in user_clubs:
        club = bot_data.clubs.get(club_name, {})
        if club.get("owner") == user_id:
            target_club = club_name
            break
    
    if not target_club:
        update.message.reply_text("❌ Вы не являетесь создателем ни одного клуба")
        return
    
    result = bot_data.request_safe_withdrawal(user_id, target_club, amount)
    
    if result == "waiting_confirmation":
        # Отправляем сообщение с кнопками подтверждения
        keyboard = [
            [
                InlineKeyboardButton("✅ Да", callback_data=f"withdraw_confirm_{amount}"),
                InlineKeyboardButton("❌ Нет", callback_data=f"withdraw_cancel_{amount}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            f"⚠️ Вы уверены, что хотите снять {amount}💰 из сейфа клуба '{target_club}'?",
            reply_markup=reply_markup
        )
    else:
        update.message.reply_text(result)

# ==================== КОМАНДЫ ДЛЯ СОЗДАТЕЛЯ ====================

def infoclub(update: Update, context: CallbackContext):
    """Информация о клубе (для создателя)"""
    user_id = update.effective_user.id
    
    if not bot_data.is_creator_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    if not context.args:
        update.message.reply_text(
            "🏰 Информация о клубе\n\n"
            "Использование: /infoclub [название клуба]\n\n"
            "Пример: /infoclub MyClub"
        )
        return
    
    club_name = context.args[0]
    club_info = bot_data.get_club_info(club_name)
    
    if not club_info:
        update.message.reply_text("❌ Клуб не найден")
        return
    
    # Детальная информация для создателя
    owner_username = bot_data.users[club_info["owner"]]["username"] if club_info["owner"] in bot_data.users else "Неизвестно"
    
    # Статистика участников
    members_by_rank = {i: 0 for i in range(1, 7)}
    for member_data in club_info["members"].values():
        rank = member_data["rank"]
        members_by_rank[rank] = members_by_rank.get(rank, 0) + 1
    
    # История транзакций сейфа
    safe_transactions = bot_data.club_safes.get(club_name, {}).get("transactions", [])
    recent_transactions = safe_transactions[-5:] if safe_transactions else []
    
    response = (
        f"🏰 ДЕТАЛЬНАЯ ИНФОРМАЦИЯ О КЛУБЕ\n\n"
        f"📛 Название: {club_name}\n"
        f"👑 Создатель: @{owner_username} (ID: {club_info['owner']})\n"
        f"👥 Участников: {club_info['members_count']}\n"
        f"💰 Сейф: {club_info['safe_balance']} монет\n"
        f"📅 Создан: {time.strftime('%Y-%m-%d %H:%M', time.localtime(club_info['created_at']))}\n\n"
        f"📊 Распределение по рангам:\n"
    )
    
    for rank in range(1, 7):
        count = members_by_rank.get(rank, 0)
        rank_name = "👑 Создатель" if rank == 6 else club_info["ranks"][rank-1] if rank <= 5 else f"Ранг {rank}"
        response += f"  {rank_name}: {count} чел.\n"
    
    if recent_transactions:
        response += f"\n💳 Последние операции сейфа:\n"
        for tx in recent_transactions:
            username = tx.get("username", f"ID:{tx['user_id']}")
            amount = tx["amount"]
            note = tx.get("note", "")
            time_str = time.strftime("%m/%d %H:%M", time.localtime(tx["timestamp"]))
            tx_type = "📥" if tx["type"] == "deposit" else "📤"
            response += f"  {tx_type} {time_str} | {username}: {amount}💰 {note}\n"
    
    # Информация о чате
    chat_messages = bot_data.club_chats.get(club_name, [])
    response += f"\n💬 Сообщений в чате: {len(chat_messages)}"
    
    update.message.reply_text(response)

def testmode(update: Update, context: CallbackContext):
    """Войти в тестовый режим"""
    user_id = update.effective_user.id
    
    if not bot_data.is_creator_authenticated(user_id):
        update.message.reply_text("❌ Авторизуйтесь как создатель: /register [пароль]")
        return
    
    result = bot_data.enter_test_mode(user_id)
    update.message.reply_text(result)

def untest(update: Update, context: CallbackContext):
    """Выйти из тестового режима"""
    user_id = update.effective_user.id
    
    if not bot_data.is_creator(user_id):
        update.message.reply_text("❌ Эта команда только для создателя")
        return
    
    result = bot_data.exit_test_mode(user_id)
    update.message.reply_text(result)

# ==================== ОБРАБОТЧИКИ КНОПОК ====================

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
        
        # Уведомляем обоих пользователей
        query.edit_message_text("✅ Запрос в друзья принят!")
        
        # Уведомляем отправителя
        try:
            requester_username = bot_data.users[user_id]["username"] or f"ID:{user_id}"
            context.bot.send_message(
                chat_id=from_user_id,
                text=f"✅ @{requester_username} принял(а) ваш запрос в друзья!"
            )
        except Exception:
            pass
    
    elif data.startswith("friend_reject_"):
        from_user_id = int(data.split("_")[2])
        bot_data.reject_friend_request(user_id, from_user_id)
        query.edit_message_text("❌ Запрос в друзья отклонен")
    
    # Обработка создания клуба
    elif data.startswith("createclub_"):
        parts = data.split("_")
        cost_type = parts[1]
        club_name = "_".join(parts[2:])
        
        result = bot_data.create_club(user_id, club_name, cost_type)
        query.edit_message_text(result)
    
    # Обработка подтверждения снятия из сейфа
    elif data.startswith("withdraw_confirm_"):
        amount = int(data.split("_")[2])
        result = bot_data.process_safe_withdrawal(user_id, True)
        query.edit_message_text(result)
    
    elif data.startswith("withdraw_cancel_"):
        amount = int(data.split("_")[2])
        result = bot_data.process_safe_withdrawal(user_id, False)
        query.edit_message_text(result)

# ==================== СУЩЕСТВУЮЩИЕ КОМАНДЫ (без изменений) ====================
# [Здесь должны быть все остальные команды из предыдущего кода:
# start, play, shop, leaderboard, stats, author, wheel, promo, repriv, q,
# help, balance, daily, transfer, regbank, bank, infobank,
# register, panel, creatorcmd, backup, globalstats, givepc,
# setdonate, message_cmd, givecash, givedonate, ban, unban, search, userinfo, announce,
# setbalance, reseteconomy, setmultiplier, resetuser, massgive, listadmins, botstats,
# exportdata, topactive, gamestats, reboot, cleanup, setwelcome, createpromo,
# testmode, addgame, massprivilege, setgladmin, logs]
# Они остаются без изменений, поэтому я их не дублирую для экономии места

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
    
    # Новые социальные команды
    dispatcher.add_handler(CommandHandler("addfriend", addfriend))
    dispatcher.add_handler(CommandHandler("messagefriend", messagefriend))
    dispatcher.add_handler(CommandHandler("createclub", createclub))
    dispatcher.add_handler(CommandHandler("club", club))
    dispatcher.add_handler(CommandHandler("crank", crank))
    dispatcher.add_handler(CommandHandler("cchat", cchat))
    dispatcher.add_handler(CommandHandler("ccmd", ccmd))
    dispatcher.add_handler(CommandHandler("csafe", csafe))
    dispatcher.add_handler(CommandHandler("csafewithdraw", csafewithdraw))
    
    # Команды авторизации
    dispatcher.add_handler(CommandHandler("register", register))
    dispatcher.add_handler(CommandHandler("panel", panel))
    dispatcher.add_handler(CommandHandler("creatorcmd", creatorcmd))
    
    # Команды для создателя
    dispatcher.add_handler(CommandHandler("backup", backup))
    dispatcher.add_handler(CommandHandler("globalstats", globalstats))
    dispatcher.add_handler(CommandHandler("givepc", givepc))
    dispatcher.add_handler(CommandHandler("infoclub", infoclub))
    dispatcher.add_handler(CommandHandler("testmode", testmode))
    dispatcher.add_handler(CommandHandler("untest", untest))
    
    # [Здесь должны быть все остальные существующие обработчики команд]
    # dispatcher.add_handler(CommandHandler("setdonate", setdonate))
    # dispatcher.add_handler(CommandHandler("message", message_cmd))
    # ... и все остальные
    
    dispatcher.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("🤖 Бот запущен и работает 24/7!")
    logger.info("💾 Система сохранения данных активирована")
    logger.info("🏦 Банковская система добавлена")
    logger.info("👥 Социальные функции активированы")
    logger.info("🏰 Система клубов добавлена")
    logger.info("🛡️ Надежная система emergency save работает")
    logger.info("👑 Создатель бота: Frapello")
    
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
