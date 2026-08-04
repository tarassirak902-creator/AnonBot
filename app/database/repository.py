import aiosqlite
import secrets
import string
from datetime import datetime, date, timedelta
from pathlib import Path
from app.core.config import (
    DEFAULT_REVEAL_COST,
    DEFAULT_WELCOME_TEXT,
)

DB_PATH = str(Path(__file__).resolve().parents[2] / "data" / "bot.db")


async def _migrate_matchmaking_tables(db: aiosqlite.Connection) -> None:
    """Recreate legacy temporary matchmaking tables in the unified format.

    Queues and active chats are transient state. User data, purchases, gifts,
    advertising and settings are not touched.
    """
    for table in ("queues", "active_chats"):
        row = await (await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )).fetchone()
        if not row:
            continue
        columns = await (await db.execute(f"PRAGMA table_info({table})")).fetchall()
        legacy_column = "chat" + "_" + "type"
        if any(column[1] == legacy_column for column in columns):
            await db.execute(f"DROP TABLE {table}")


async def init_db():
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA busy_timeout=5000;")
        await db.execute("PRAGMA synchronous=NORMAL;")
        await _migrate_matchmaking_tables(db)
        
        await db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                joined_date TEXT,
                blocked INTEGER DEFAULT 0,
                warnings INTEGER DEFAULT 0,
                sent_gifts INTEGER DEFAULT 0,
                received_gifts INTEGER DEFAULT 0,
                complaints_sent INTEGER DEFAULT 0,
                total_stars_spent INTEGER DEFAULT 0,
                referred_by INTEGER DEFAULT NULL,
                reward_claimed INTEGER DEFAULT 0,
                chat_time_seconds INTEGER DEFAULT 0,
                current_chat_start TEXT DEFAULT NULL,
                messages_count INTEGER DEFAULT 0,
                stars_balance INTEGER DEFAULT 0,
                is_vip INTEGER DEFAULT 0,
                vip_expires_at TEXT DEFAULT NULL,
                blocked_until TEXT DEFAULT NULL,
                last_activity TEXT DEFAULT NULL,
                ref_code TEXT DEFAULT NULL,
                completed_dialogs INTEGER DEFAULT 0,
                referred_at TEXT DEFAULT NULL,
                referral_rewarded_at TEXT DEFAULT NULL
            );
            CREATE TABLE IF NOT EXISTS active_chats (
                user_id INTEGER PRIMARY KEY,
                partner_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS queues (
                user_id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS gifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                emoji TEXT,
                price_stars INTEGER
            );
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                buyer_id INTEGER,
                receiver_id INTEGER,
                gift_id INTEGER,
                price_stars INTEGER,
                type TEXT,
                timestamp TEXT
            );
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_id INTEGER,
                reported_id INTEGER,
                reason TEXT,
                timestamp TEXT
            );
            CREATE TABLE IF NOT EXISTS banned_words (
                word TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                timestamp TEXT
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS withdraw_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                status TEXT DEFAULT 'pending',
                timestamp TEXT,
                processed_by INTEGER DEFAULT NULL,
                processed_at TEXT DEFAULT NULL,
                log_chat_id INTEGER DEFAULT NULL,
                log_message_id INTEGER DEFAULT NULL
            );
            CREATE TABLE IF NOT EXISTS admin_action_claims (
                action_key TEXT PRIMARY KEY,
                admin_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                processed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS game_duels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER,
                partner_id INTEGER,
                amount INTEGER,
                status TEXT DEFAULT 'waiting',
                game_type TEXT DEFAULT 'darts'
            );
            CREATE TABLE IF NOT EXISTS advertising_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                advertiser_id INTEGER NOT NULL,
                campaign_type TEXT NOT NULL CHECK(campaign_type IN ('post','subscription')),
                status TEXT NOT NULL DEFAULT 'pending_moderation',
                target_amount INTEGER NOT NULL,
                completed_amount INTEGER NOT NULL DEFAULT 0,
                package_size INTEGER NOT NULL,
                package_price_stars INTEGER NOT NULL,
                total_price_stars INTEGER NOT NULL,
                source_chat_id INTEGER,
                source_message_id INTEGER,
                source_preview_text TEXT,
                channel_ref TEXT,
                community_type TEXT,
                community_title TEXT,
                community_url TEXT,
                telegram_payment_charge_id TEXT,
                moderated_by INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                started_at TEXT,
                completed_at TEXT,
                last_delivery_at TEXT,
                rejection_reason TEXT
            );
            CREATE TABLE IF NOT EXISTS advertising_impressions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                dialog_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'reserved',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TEXT,
                UNIQUE(dialog_key, user_id)
            );
            CREATE TABLE IF NOT EXISTS sponsor_subscriptions (
                campaign_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                confirmed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(campaign_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS anonymous_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                public_id TEXT NOT NULL UNIQUE,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                answer_text TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                read_at TEXT,
                answered_at TEXT,
                author_revealed INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS question_link_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                visitor_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        for column_sql in (
            "ALTER TABLE advertising_orders ADD COLUMN community_type TEXT",
            "ALTER TABLE advertising_orders ADD COLUMN community_title TEXT",
            "ALTER TABLE advertising_orders ADD COLUMN community_url TEXT",
            "ALTER TABLE advertising_orders ADD COLUMN source_preview_text TEXT",
            "ALTER TABLE advertising_orders ADD COLUMN rejection_reason TEXT"
        ):
            try:
                await db.execute(column_sql)
            except Exception:
                pass

        # Одноразовая миграция старой схемы matchmaking.
        # Очередь и активные диалоги являются временными данными, поэтому очищаются.
        queue_columns = await (await db.execute("PRAGMA table_info(queues)")).fetchall()
        if len(queue_columns) != 2:
            await db.executescript('''
                DROP TABLE IF EXISTS queues_new;
                CREATE TABLE queues_new (
                    user_id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                DROP TABLE queues;
                ALTER TABLE queues_new RENAME TO queues;
            ''')

        chat_columns = await (await db.execute("PRAGMA table_info(active_chats)")).fetchall()
        if len(chat_columns) != 3:
            await db.executescript('''
                DROP TABLE IF EXISTS active_chats_new;
                CREATE TABLE active_chats_new (
                    user_id INTEGER PRIMARY KEY,
                    partner_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                DROP TABLE active_chats;
                ALTER TABLE active_chats_new RENAME TO active_chats;
            ''')

        await db.executescript('''
            CREATE INDEX IF NOT EXISTS idx_queues_created ON queues(created_at);
            CREATE INDEX IF NOT EXISTS idx_active_chats_partner ON active_chats(partner_id);
            CREATE INDEX IF NOT EXISTS idx_users_blocked ON users(blocked);
            CREATE INDEX IF NOT EXISTS idx_logs_user_timestamp ON logs(user_id, timestamp);
        ''')
        
        async def ensure_column(
            table_name: str,
            column_name: str,
            column_definition: str,
        ) -> None:
            """Добавляет колонку только в случае её отсутствия."""
            cursor = await db.execute(
                f"PRAGMA table_info({table_name})"
            )
            columns = await cursor.fetchall()
            existing_names = {column[1] for column in columns}

            if column_name not in existing_names:
                await db.execute(
                    f"ALTER TABLE {table_name} "
                    f"ADD COLUMN {column_name} {column_definition}"
                )

        await ensure_column(
            "users",
            "stars_balance",
            "INTEGER DEFAULT 0",
        )
        await ensure_column(
            "game_duels",
            "game_type",
            "TEXT DEFAULT 'darts'",
        )
        await ensure_column(
            "users",
            "is_vip",
            "INTEGER DEFAULT 0",
        )

        await ensure_column(
            "users",
            "vip_expires_at",
            "TEXT DEFAULT NULL",
        )
        await ensure_column(
            "users",
            "blocked_until",
            "TEXT DEFAULT NULL",
        )

        await ensure_column(
            "users",
            "search_game_vip_won_until",
            "TEXT DEFAULT NULL",
        )
        await ensure_column(
            "users",
            "search_game_discount_status",
            "TEXT DEFAULT NULL",
        )
        await ensure_column(
            "users",
            "search_game_discount_partner_id",
            "INTEGER DEFAULT NULL",
        )
        await ensure_column(
            "users",
            "search_game_stars_date",
            "TEXT DEFAULT NULL",
        )
        await ensure_column(
            "users",
            "search_game_stars_today",
            "INTEGER DEFAULT 0",
        )

        # Правило трёх предупреждений:
        # старые значения выше лимита нормализуются,
        # а пользователь блокируется бессрочно.
        await db.execute(
            "UPDATE users SET warnings=3 WHERE warnings > 3"
        )
        await db.execute(
            "UPDATE users "
            "SET blocked=1, blocked_until=NULL "
            "WHERE warnings >= 3"
        )
        await ensure_column(
            "users",
            "last_activity",
            "TEXT DEFAULT NULL",
        )
        await ensure_column(
            "users",
            "ref_code",
            "TEXT DEFAULT NULL",
        )
        await ensure_column(
            "users",
            "completed_dialogs",
            "INTEGER DEFAULT 0",
        )
        await ensure_column(
            "users",
            "referred_at",
            "TEXT DEFAULT NULL",
        )
        await ensure_column(
            "users",
            "referral_rewarded_at",
            "TEXT DEFAULT NULL",
        )
        await ensure_column(
            "users",
            "question_token",
            "TEXT DEFAULT NULL",
        )
        await ensure_column(
            "users",
            "questions_enabled",
            "INTEGER DEFAULT 1",
        )
        await ensure_column(
            "users",
            "question_notifications",
            "INTEGER DEFAULT 1",
        )
        await ensure_column(
            "users",
            "questions_intro_sent",
            "INTEGER DEFAULT 0",
        )
        await ensure_column(
            "anonymous_questions",
            "answer_read_at",
            "TEXT DEFAULT NULL",
        )
        await ensure_column(
            "anonymous_questions",
            "question_chat_pending",
            "INTEGER DEFAULT 0",
        )
        await ensure_column(
            "anonymous_questions",
            "answer_chat_pending",
            "INTEGER DEFAULT 0",
        )

        await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_ref_code ON users(ref_code) WHERE ref_code IS NOT NULL"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by)"
        )
        await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_question_token "
            "ON users(question_token) WHERE question_token IS NOT NULL"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_questions_receiver_status "
            "ON anonymous_questions(receiver_id, status, created_at DESC)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_question_visits_owner "
            "ON question_link_visits(owner_id, created_at)"
        )
        await ensure_column(
            "withdraw_requests",
            "processed_by",
            "INTEGER DEFAULT NULL",
        )
        await ensure_column(
            "withdraw_requests",
            "processed_at",
            "TEXT DEFAULT NULL",
        )
        await ensure_column(
            "withdraw_requests",
            "log_chat_id",
            "INTEGER DEFAULT NULL",
        )
        await ensure_column(
            "withdraw_requests",
            "log_message_id",
            "INTEGER DEFAULT NULL",
        )

        await ensure_column(
            "queues",
            "created_at",
            "TEXT",
        )
        await ensure_column(
            "active_chats",
            "created_at",
            "TEXT",
        )
        await db.execute("UPDATE queues SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)")
        await db.execute("UPDATE active_chats SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)")

        await db.executemany(
            "INSERT OR IGNORE INTO settings VALUES (?, ?)",
            [("reveal_cost", DEFAULT_REVEAL_COST),
             ("welcome_text", DEFAULT_WELCOME_TEXT),
             ("ad_post_package_price_stars", "150"),
             ("ad_subscriber_package_price_stars", "100"),
             ("ad_post_min_quantity", "100"),
             ("ad_subscriber_min_quantity", "50")]
        )
        
        default_gifts = [
            ("Сердце", "💖", 15), ("Мишка", "🧸", 15), ("Подарок", "🎁", 25),
            ("Роза", "🌹", 25), ("Торт", "🎂", 50), ("Букет", "💐", 50),
            ("Ракета", "🚀", 50), ("Кубок", "🏆", 100), ("Кольцо", "💍", 100),
            ("Алмаз", "💎", 100), ("Шампанское", "🍾", 50), ("Факел", "🗽", 385)
        ]
        
        cursor = await db.execute("SELECT COUNT(*) FROM gifts")
        if (await cursor.fetchone())[0] == 0:
            await db.executemany(
                "INSERT INTO gifts (name, emoji, price_stars) VALUES (?, ?, ?)",
                default_gifts
            )
        await db.commit()

# ---------- ПОЛЬЗОВАТЕЛИ И БАЛАНС ----------
async def add_user(user_id, username, first_name, last_name):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users(user_id,username,first_name,last_name,joined_date,stars_balance) VALUES (?,?,?,?,?, 0)",
            (user_id, username, first_name, last_name, datetime.now().isoformat()))
        await db.execute(
            "UPDATE users SET username=?,first_name=?,last_name=? WHERE user_id=?",
            (username, first_name, last_name, user_id))
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        return await cursor.fetchone()

async def get_user_balance(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute("SELECT stars_balance FROM users WHERE user_id=?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row and row[0] is not None else 0

async def add_user_balance(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute("UPDATE users SET stars_balance = stars_balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def deduct_user_balance(user_id: int, amount: int) -> bool:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute("SELECT stars_balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        current_balance = row[0] if row and row[0] else 0
        if current_balance >= amount:
            await db.execute("UPDATE users SET stars_balance = stars_balance - ? WHERE user_id = ?", (amount, user_id))
            await db.commit()
            return True
        return False

# ---------- VIP СТАТУС (TELEGRAM STARS ПОДПИСКА) ----------
async def is_user_vip(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute("SELECT is_vip, vip_expires_at FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row or row[0] != 1:
            return False
        
        # Дополнительно проверяем срок действия
        if row[1]:
            try:
                exp_date = datetime.fromisoformat(row[1])
                if datetime.now() > exp_date:
                    return False
            except Exception:
                pass
        return True

async def set_user_vip(user_id: int, is_vip: bool):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        exp_time = (datetime.now() + timedelta(days=1, hours=2)).isoformat() if is_vip else None
        await db.execute("UPDATE users SET is_vip = ?, vip_expires_at = ? WHERE user_id = ?", (int(is_vip), exp_time, user_id))
        await db.commit()

async def extend_user_vip_days(user_id: int, days: int = 1):
    """Продлевает VIP-статус пользователя на N дней при автосписании от Telegram"""
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute("SELECT vip_expires_at FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        now = datetime.now()

        current_exp = None
        if row and row[0]:
            try:
                current_exp = datetime.fromisoformat(row[0])
            except (TypeError, ValueError):
                current_exp = None

        if current_exp and current_exp > now:
            new_exp = current_exp + timedelta(days=days)
        else:
            new_exp = now + timedelta(days=days, hours=2)  # Запас 2 часа на задержку платежа

        await db.execute("UPDATE users SET is_vip = 1, vip_expires_at = ? WHERE user_id = ?", (new_exp.isoformat(), user_id))
        await db.commit()

async def check_and_expire_vips():
    """Фоновая проверка истекших VIP-подписок (если Telegram не списал средства)"""
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute("SELECT user_id, vip_expires_at FROM users WHERE is_vip = 1")
        rows = await cursor.fetchall()
        now = datetime.now()
        expired_ids = []

        for uid, exp_str in rows:
            if exp_str:
                try:
                    if datetime.fromisoformat(exp_str) < now:
                        expired_ids.append(uid)
                except Exception:
                    expired_ids.append(uid)

        for uid in expired_ids:
            await db.execute("UPDATE users SET is_vip = 0, vip_expires_at = NULL WHERE user_id = ?", (uid,))
        await db.commit()
        return expired_ids

async def update_user_stats(user_id, sent_gifts=0, received_gifts=0, complaints=0, stars=0):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute(
            "UPDATE users SET sent_gifts=sent_gifts+?, received_gifts=received_gifts+?, complaints_sent=complaints_sent+?, total_stars_spent=total_stars_spent+? WHERE user_id=?",
            (sent_gifts, received_gifts, complaints, stars, user_id))
        await db.commit()

async def block_user(user_id, blocked=True, until: datetime | None = None):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute(
            "UPDATE users SET blocked=?, blocked_until=? WHERE user_id=?",
            (int(blocked), until.isoformat() if blocked and until else None, user_id),
        )
        await db.commit()

async def is_user_blocked(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        row = await (await db.execute(
            "SELECT blocked, blocked_until FROM users WHERE user_id=?", (user_id,)
        )).fetchone()
        if not row or not row[0]:
            return False
        if row[1]:
            try:
                if datetime.now() >= datetime.fromisoformat(row[1]):
                    await db.execute(
                        "UPDATE users SET blocked=0, blocked_until=NULL WHERE user_id=?", (user_id,)
                    )
                    await db.commit()
                    return False
            except (ValueError, TypeError):
                pass
        return True

async def get_user_block_status(user_id: int):
    """Return (is_blocked, blocked_until). Expired temporary blocks are cleared."""
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        row = await (await db.execute(
            "SELECT blocked, blocked_until FROM users WHERE user_id=?", (user_id,)
        )).fetchone()
        if not row or not row[0]:
            return False, None

        blocked_until = None
        if row[1]:
            try:
                blocked_until = datetime.fromisoformat(row[1])
                if datetime.now() >= blocked_until:
                    await db.execute(
                        "UPDATE users SET blocked=0, blocked_until=NULL WHERE user_id=?",
                        (user_id,),
                    )
                    await db.commit()
                    return False, None
            except (ValueError, TypeError):
                blocked_until = None

        return True, blocked_until

async def warn_user(user_id: int) -> tuple[int, bool]:
    """Add one warning, cap at three, and permanently ban at the threshold.

    Returns ``(warnings_count, auto_banned)``.
    """
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute("BEGIN IMMEDIATE")
        row = await (await db.execute(
            "SELECT warnings FROM users WHERE user_id=?", (user_id,)
        )).fetchone()
        current = int(row[0] or 0) if row else 0
        warnings_count = min(3, current + 1)
        auto_banned = warnings_count >= 3
        if auto_banned:
            await db.execute(
                "UPDATE users SET warnings=?, blocked=1, blocked_until=NULL WHERE user_id=?",
                (warnings_count, user_id),
            )
        else:
            await db.execute(
                "UPDATE users SET warnings=? WHERE user_id=?",
                (warnings_count, user_id),
            )
        await db.commit()
        return warnings_count, auto_banned

# ---------- ДУЭЛИ МИНИ-ИГР ----------
async def create_game_duel(creator_id: int, partner_id: int, amount: int, game_type: str = "darts") -> int:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute(
            "INSERT INTO game_duels (creator_id, partner_id, amount, status, game_type) VALUES (?, ?, ?, 'waiting', ?)",
            (creator_id, partner_id, amount, game_type)
        )
        await db.commit()
        return cursor.lastrowid

async def get_game_duel(duel_id: int):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute("SELECT * FROM game_duels WHERE id = ?", (duel_id,))
        return await cursor.fetchone()

async def update_game_duel_status(duel_id: int, status: str):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute("UPDATE game_duels SET status = ? WHERE id = ?", (status, duel_id))
        await db.commit()

# ---------- ОЧЕРЕДИ И МАТЧМЕЙКИНГ ----------
async def add_to_queue(user_id):
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute(
            "INSERT INTO queues(user_id, created_at) VALUES (?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(user_id) DO UPDATE SET created_at=CURRENT_TIMESTAMP",
            (user_id,),
        )
        await conn.commit()

async def remove_from_queue(user_id):
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("DELETE FROM queues WHERE user_id=?", (user_id,))
        await conn.commit()

async def is_in_queue(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        row = await (await conn.execute(
            "SELECT 1 FROM queues WHERE user_id=? LIMIT 1", (user_id,)
        )).fetchone()
        return row is not None

async def remove_stale_queue_entries(max_age_seconds: int = 360) -> int:
    """Delete abandoned queue rows and return the number removed."""
    safe_age = max(1, int(max_age_seconds))
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        cursor = await conn.execute(
            "DELETE FROM queues "
            "WHERE created_at <= datetime('now', ?)",
            (f"-{safe_age} seconds",),
        )
        await conn.commit()
        return max(0, cursor.rowcount or 0)

async def try_match_user(user_id: int):
    """Атомарно добавляет пользователя в единую очередь или создаёт пару."""
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        try:
            await conn.execute("BEGIN IMMEDIATE")
            await conn.execute("DELETE FROM queues WHERE user_id=?", (user_id,))
            current = await (await conn.execute(
                "SELECT partner_id FROM active_chats WHERE user_id=?", (user_id,)
            )).fetchone()
            if current:
                await conn.rollback()
                return None

            row = await (await conn.execute(
                """SELECT q.user_id
                   FROM queues q
                   LEFT JOIN active_chats a ON a.user_id=q.user_id
                   LEFT JOIN users u ON u.user_id=q.user_id
                  WHERE q.user_id!=?
                    AND a.user_id IS NULL
                    AND COALESCE(u.blocked, 0)=0
                  ORDER BY q.created_at ASC, q.rowid ASC
                  LIMIT 1""",
                (user_id,),
            )).fetchone()

            if not row:
                await conn.execute(
                    "INSERT INTO queues(user_id, created_at) VALUES (?, CURRENT_TIMESTAMP)",
                    (user_id,),
                )
                await conn.commit()
                return None

            partner_id = row[0]
            await conn.execute("DELETE FROM queues WHERE user_id IN (?, ?)", (user_id, partner_id))
            await conn.execute("DELETE FROM active_chats WHERE user_id IN (?, ?)", (user_id, partner_id))
            await conn.executemany(
                "INSERT INTO active_chats(user_id, partner_id, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                [(user_id, partner_id), (partner_id, user_id)],
            )
            await conn.commit()
            return partner_id
        except Exception:
            await conn.rollback()
            raise

async def clear_all_chats_and_queues():
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("DELETE FROM active_chats")
        await conn.execute("DELETE FROM queues")
        await conn.commit()

async def repair_matchmaking_state():
    """Удаляет односторонние пары и конфликтующие записи после аварийного рестарта."""
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        await conn.execute(
            """DELETE FROM active_chats
               WHERE NOT EXISTS (
                   SELECT 1 FROM active_chats reciprocal
                   WHERE reciprocal.user_id=active_chats.partner_id
                     AND reciprocal.partner_id=active_chats.user_id
               )"""
        )
        await conn.execute("DELETE FROM queues WHERE user_id IN (SELECT user_id FROM active_chats)")
        await conn.execute("DELETE FROM queues WHERE user_id IN (SELECT user_id FROM users WHERE blocked=1)")
        await conn.commit()

# ---------- АКТИВНЫЕ ДИАЛОГИ ----------
async def end_chat(user_id):
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        row = await (await conn.execute(
            "SELECT partner_id FROM active_chats WHERE user_id=?", (user_id,)
        )).fetchone()
        if not row:
            await conn.execute("DELETE FROM queues WHERE user_id=?", (user_id,))
            await conn.commit()
            return None
        partner_id = row[0]
        await conn.execute("DELETE FROM active_chats WHERE user_id IN (?, ?)", (user_id, partner_id))
        await conn.execute("DELETE FROM queues WHERE user_id IN (?, ?)", (user_id, partner_id))
        await conn.commit()
        return partner_id

async def get_partner(user_id):
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        row = await (await conn.execute(
            """SELECT a.partner_id
               FROM active_chats a
               JOIN active_chats b ON b.user_id=a.partner_id AND b.partner_id=a.user_id
              WHERE a.user_id=?""",
            (user_id,),
        )).fetchone()
        if row:
            return row[0]
        await conn.execute("DELETE FROM active_chats WHERE user_id=?", (user_id,))
        await conn.commit()
        return None

# ---------- ПОДАРКИ И ПОКУПКИ ----------
async def get_all_gifts():
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute("SELECT * FROM gifts")
        return await cursor.fetchall()

async def get_gift(gift_id):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute("SELECT name, emoji, price_stars FROM gifts WHERE id=?", (gift_id,))
        return await cursor.fetchone()

async def add_gift(name, emoji, price):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute("INSERT INTO gifts (name, emoji, price_stars) VALUES (?, ?, ?)", (name, emoji, price))
        await db.commit()

async def delete_gift(gift_id):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute("DELETE FROM gifts WHERE id=?", (gift_id,))
        await db.commit()

async def add_purchase(buyer_id, receiver_id, gift_id, price_stars, purchase_type):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute("INSERT INTO purchases (buyer_id, receiver_id, gift_id, price_stars, type, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                         (buyer_id, receiver_id, gift_id, price_stars, purchase_type, datetime.now().isoformat()))
        await db.commit()

async def get_revealed_partners(user_id):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute(
            "SELECT receiver_id, timestamp FROM purchases WHERE buyer_id=? AND type='reveal' ORDER BY timestamp DESC",
            (user_id,))
        return await cursor.fetchall()

async def get_user_sent_gifts(user_id: int):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute("""
            SELECT g.emoji, g.name, p.price_stars, p.timestamp 
            FROM purchases p
            LEFT JOIN gifts g ON p.gift_id = g.id
            WHERE p.buyer_id = ? AND p.type = 'gift'
            ORDER BY p.id DESC LIMIT 10
        """, (user_id,))
        return await cursor.fetchall()

async def get_user_received_gifts(user_id: int):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute("""
            SELECT g.emoji, g.name, p.price_stars, p.timestamp 
            FROM purchases p
            LEFT JOIN gifts g ON p.gift_id = g.id
            WHERE p.receiver_id = ? AND p.type = 'gift'
            ORDER BY p.id DESC LIMIT 10
        """, (user_id,))
        return await cursor.fetchall()

async def get_user_received_gifts_summary(user_id: int):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute("""
            SELECT g.emoji, g.name, COUNT(*) as gift_count
            FROM purchases p
            JOIN gifts g ON p.gift_id = g.id
            WHERE p.receiver_id = ? AND p.type = 'gift'
            GROUP BY g.id
            ORDER BY gift_count DESC
        """, (user_id,))
        return await cursor.fetchall()

# ---------- ЗАЯВКИ НА ВЫВОД ----------
async def create_withdraw_request_atomic(user_id: int, amount: int) -> int | None:
    """Атомарно резервирует баланс и создаёт заявку, исключая двойной вывод."""
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute("PRAGMA busy_timeout=10000")
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute(
            "UPDATE users SET stars_balance=stars_balance-? WHERE user_id=? AND stars_balance>=?",
            (amount, user_id, amount),
        )
        if cursor.rowcount != 1:
            await db.rollback()
            return None
        cursor = await db.execute(
            "INSERT INTO withdraw_requests (user_id, amount, status, timestamp) VALUES (?, ?, 'pending', ?)",
            (user_id, amount, datetime.now().isoformat()),
        )
        await db.commit()
        return cursor.lastrowid

async def create_withdraw_request(user_id: int, amount: int) -> int:
    req_id = await create_withdraw_request_atomic(user_id, amount)
    if req_id is None:
        raise ValueError("Недостаточно средств")
    return req_id

async def get_withdraw_request(request_id: int):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute("SELECT * FROM withdraw_requests WHERE id = ?", (request_id,))
        return await cursor.fetchone()

async def set_withdraw_log_message(request_id: int, chat_id: int, message_id: int) -> None:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute(
            "UPDATE withdraw_requests SET log_chat_id=?, log_message_id=? WHERE id=?",
            (chat_id, message_id, request_id),
        )
        await db.commit()

async def get_pending_withdraw_requests(limit: int = 50):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        return await (await db.execute(
            "SELECT w.id,w.user_id,w.amount,w.timestamp,u.username,u.first_name,u.last_name "
            "FROM withdraw_requests w LEFT JOIN users u ON u.user_id=w.user_id "
            "WHERE w.status='pending' ORDER BY w.id ASC LIMIT ?", (limit,)
        )).fetchall()

async def process_withdraw_request(request_id: int, status: str, admin_id: int):
    """Атомарно обрабатывает заявку. Возвращает обновлённую запись или None."""
    if status not in {"approved", "rejected"}:
        raise ValueError("Недопустимый статус")
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute("PRAGMA busy_timeout=10000")
        await db.execute("BEGIN IMMEDIATE")
        req = await (await db.execute(
            "SELECT * FROM withdraw_requests WHERE id=?", (request_id,)
        )).fetchone()
        if not req or req[3] != "pending":
            await db.rollback()
            return None
        now = datetime.now().isoformat()
        cur = await db.execute(
            "UPDATE withdraw_requests SET status=?,processed_by=?,processed_at=? "
            "WHERE id=? AND status='pending'",
            (status, admin_id, now, request_id),
        )
        if cur.rowcount != 1:
            await db.rollback()
            return None
        if status == "rejected":
            await db.execute(
                "UPDATE users SET stars_balance=stars_balance+? WHERE user_id=?",
                (req[2], req[1]),
            )
        await db.commit()
        return await get_withdraw_request(request_id)

async def claim_admin_action(action_key: str, admin_id: int, action: str) -> bool:
    """Атомарная защита от повторной обработки кнопок несколькими админами."""
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        try:
            await db.execute(
                "INSERT INTO admin_action_claims(action_key,admin_id,action,processed_at) VALUES(?,?,?,?)",
                (action_key, admin_id, action, datetime.now().isoformat()),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def update_withdraw_status(request_id: int, status: str):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute("UPDATE withdraw_requests SET status = ? WHERE id = ?", (status, request_id))
        await db.commit()

# ---------- ЖАЛОБЫ И ЗАПРЕЩЁННЫЕ СЛОВА ----------
async def add_complaint(reporter_id, reported_id, reason):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute("INSERT INTO complaints (reporter_id, reported_id, reason, timestamp) VALUES (?, ?, ?, ?)",
                         (reporter_id, reported_id, reason, datetime.now().isoformat()))
        await db.commit()

async def contains_banned_word(text):
    if not text: return False
    text_lower = text.lower()
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute("SELECT word FROM banned_words")
        words = await cursor.fetchall()
        for (word,) in words:
            if word.lower() in text_lower: return True
    return False

async def add_banned_word(word):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute("INSERT OR IGNORE INTO banned_words VALUES (?)", (word.lower(),))
        await db.commit()

async def remove_banned_word(word):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute("DELETE FROM banned_words WHERE word=?", (word.lower(),))
        await db.commit()

async def get_banned_words():
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute("SELECT word FROM banned_words")
        return [row[0] for row in await cursor.fetchall()]

# ---------- НАСТРОЙКИ, ЛОГИ, СТАТИСТИКА ----------
async def get_setting(key):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else None

async def set_setting(key, value):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, str(value)))
        await db.commit()

async def log_action(user_id, action, details=""):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute("INSERT INTO logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
                         (user_id, action, details, datetime.now().isoformat()))
        await db.commit()

async def get_statistics():
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        stats = {}
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        stats['total_users'] = (await cursor.fetchone())[0]
        today = date.today().isoformat()
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE joined_date LIKE ?", (f"{today}%",))
        stats['new_today'] = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM queues")
        stats['queue_count'] = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(DISTINCT user_id) FROM active_chats")
        stats['active_chats'] = (await cursor.fetchone())[0] // 2
        cursor = await db.execute("SELECT COUNT(*) FROM purchases WHERE type='gift'")
        stats['total_gifts_sent'] = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM purchases WHERE type='gift' AND timestamp LIKE ?", (f"{today}%",))
        stats['gifts_today'] = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT SUM(price_stars) FROM purchases")
        stats['total_stars'] = (await cursor.fetchone())[0] or 0
        cursor = await db.execute("SELECT COUNT(*) FROM purchases WHERE type='reveal'")
        stats['reveal_count'] = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM complaints")
        stats['total_complaints'] = (await cursor.fetchone())[0]
        cursor = await db.execute(
            "SELECT COUNT(*) FROM users WHERE is_vip=1 AND (vip_expires_at IS NULL OR vip_expires_at > ?)",
            (datetime.now().isoformat(),),
        )
        stats['active_vip_users'] = (await cursor.fetchone())[0]
        cursor = await db.execute(
            "SELECT COUNT(*) FROM logs WHERE action='successful_payment' AND details LIKE 'vip_subscription%'"
        )
        stats['vip_purchases'] = (await cursor.fetchone())[0]
        return stats

async def get_all_active_users():
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE blocked=0")
        return [row[0] for row in await cursor.fetchall()]

async def get_inactive_users():
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cutoff = (datetime.now() - timedelta(hours=12)).isoformat()
        cursor = await db.execute("""
            SELECT user_id FROM users
            WHERE blocked = 0
              AND COALESCE(last_activity, joined_date) <= ?
              AND user_id NOT IN (SELECT user_id FROM active_chats)
              AND user_id NOT IN (SELECT user_id FROM queues)
            ORDER BY COALESCE(last_activity, joined_date) ASC
            LIMIT 100
        """, (cutoff,))
        rows = await cursor.fetchall()
        return [r[0] for r in rows]

# ---------- РЕФЕРАЛЫ И АКТИВНОСТЬ ----------
REFERRAL_REWARD_STARS = 50
REFERRAL_REQUIRED_DIALOGS = 5



async def refresh_user_session(user_id: int, username: str, first_name: str, last_name: str):
    """Актуализирует Telegram-профиль и гарантирует свободный статус пользователя."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute("PRAGMA busy_timeout=10000")
        await db.execute("BEGIN IMMEDIATE")
        await db.execute(
            """
            INSERT INTO users
                (user_id, username, first_name, last_name, joined_date,
                 reward_claimed, chat_time_seconds, messages_count,
                 completed_dialogs, stars_balance, last_activity)
            VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0, 0, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                current_chat_start=NULL,
                last_activity=excluded.last_activity
            """,
            (user_id, username, first_name, last_name, now, now),
        )
        await db.execute("DELETE FROM queues WHERE user_id=?", (user_id,))
        await db.execute("DELETE FROM active_chats WHERE user_id=?", (user_id,))
        await db.commit()
    await ensure_ref_code(user_id)


async def set_chat_start_time(user_id: int):
    now_str = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute(
            "UPDATE users SET current_chat_start=? WHERE user_id=?",
            (now_str, user_id),
        )
        await db.commit()


async def add_completed_chat_time(user_id: int) -> bool:
    """Завершает сессию и засчитывает диалог, если он длился не менее 60 секунд."""
    min_completed_seconds = 60

    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute("PRAGMA busy_timeout=10000")
        await db.execute("BEGIN IMMEDIATE")

        row = await (
            await db.execute(
                "SELECT current_chat_start FROM users WHERE user_id=?",
                (user_id,),
            )
        ).fetchone()

        if not row or not row[0]:
            await db.rollback()
            return False

        try:
            start_time = datetime.fromisoformat(row[0])
            duration_sec = max(
                0,
                int((datetime.now() - start_time).total_seconds()),
            )
        except (TypeError, ValueError):
            duration_sec = 0

        cursor = await db.execute(
            """
            UPDATE users
            SET chat_time_seconds=chat_time_seconds+?,
                completed_dialogs=completed_dialogs+
                    CASE WHEN ? >= ? THEN 1 ELSE 0 END,
                current_chat_start=NULL,
                last_activity=?
            WHERE user_id=?
              AND current_chat_start IS NOT NULL
            """,
            (
                duration_sec,
                duration_sec,
                min_completed_seconds,
                datetime.now().isoformat(),
                user_id,
            ),
        )

        await db.commit()
        return bool(cursor.rowcount)

async def register_user_activity(user_id: int):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute(
            """UPDATE users
               SET messages_count=messages_count+1, last_activity=?
               WHERE user_id=?""",
            (datetime.now().isoformat(), user_id),
        )
        await db.commit()

def _new_ref_code(length: int = 8) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def ensure_ref_code(user_id: int) -> str:
    """Возвращает постоянный уникальный реферальный код пользователя."""
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        row = await (await conn.execute(
            "SELECT ref_code FROM users WHERE user_id=?", (user_id,)
        )).fetchone()
        if row and row[0]:
            return row[0]

        for _ in range(20):
            code = _new_ref_code()
            try:
                cursor = await conn.execute(
                    "UPDATE users SET ref_code=? WHERE user_id=? AND ref_code IS NULL",
                    (code, user_id),
                )
                await conn.commit()
                if cursor.rowcount:
                    return code
                row = await (await conn.execute(
                    "SELECT ref_code FROM users WHERE user_id=?", (user_id,)
                )).fetchone()
                if row and row[0]:
                    return row[0]
            except aiosqlite.IntegrityError:
                await conn.rollback()
        raise RuntimeError("Не удалось создать уникальный реферальный код")


async def get_user_id_by_ref_code(ref_code: str) -> int | None:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        row = await (await conn.execute(
            "SELECT user_id FROM users WHERE ref_code=?", (ref_code,)
        )).fetchone()
        return int(row[0]) if row else None


async def bind_referrer_once(user_id: int, referrer_id: int) -> bool:
    """Привязывает пригласившего один раз. Самоприглашение исключено."""
    if not referrer_id or user_id == referrer_id:
        return False
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        exists = await (await conn.execute(
            "SELECT 1 FROM users WHERE user_id=?", (referrer_id,)
        )).fetchone()
        if not exists:
            return False
        cursor = await conn.execute(
            """UPDATE users
               SET referred_by=?, referred_at=?
               WHERE user_id=? AND referred_by IS NULL""",
            (referrer_id, now, user_id),
        )
        await conn.commit()
        return bool(cursor.rowcount)


async def add_user_with_ref(user_id: int, username: str, first_name: str, last_name: str, referrer_id: int = None):
    """Совместимость со старыми числовыми ref-ссылками."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute(
            """INSERT INTO users
               (user_id, username, first_name, last_name, joined_date, referred_by,
                referred_at, reward_claimed, chat_time_seconds, messages_count,
                completed_dialogs, stars_balance, last_activity)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 username=excluded.username, first_name=excluded.first_name,
                 last_name=excluded.last_name, last_activity=excluded.last_activity""",
            (user_id, username, first_name, last_name, now, referrer_id,
             now if referrer_id else None, now),
        )
        await conn.commit()
    await ensure_ref_code(user_id)


async def get_eligible_referrals(required_dialogs: int = REFERRAL_REQUIRED_DIALOGS):
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        cursor = await conn.execute(
            """SELECT user_id, referred_by
               FROM users
               WHERE referred_by IS NOT NULL
                 AND reward_claimed=0
                 AND completed_dialogs >= ?""",
            (required_dialogs,),
        )
        return await cursor.fetchall()


async def claim_referral_reward(invited_user_id: int, referrer_id: int, stars_amount: int = REFERRAL_REWARD_STARS) -> bool:
    """Атомарно помечает награду и начисляет её только один раз."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        cursor = await conn.execute(
            """UPDATE users
               SET reward_claimed=1, referral_rewarded_at=?
               WHERE user_id=? AND referred_by=? AND reward_claimed=0""",
            (now, invited_user_id, referrer_id),
        )
        if not cursor.rowcount:
            await conn.rollback()
            return False
        await conn.execute(
            "UPDATE users SET stars_balance=stars_balance+? WHERE user_id=?",
            (stars_amount, referrer_id),
        )
        await conn.execute(
            "INSERT INTO logs(user_id, action, details, timestamp) VALUES(?,?,?,?)",
            (referrer_id, "referral_reward", f"invited={invited_user_id};stars={stars_amount}", now),
        )
        await conn.commit()
        return True


async def get_user_referrals_stats(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        row = await (await conn.execute(
            """SELECT COUNT(*),
                      SUM(CASE WHEN reward_claimed=1 THEN 1 ELSE 0 END),
                      SUM(CASE WHEN reward_claimed=0 THEN 1 ELSE 0 END)
               FROM users WHERE referred_by=?""",
            (user_id,),
        )).fetchone()
        total = int(row[0] or 0)
        active = int(row[1] or 0)
        pending = int(row[2] or 0)
        return {
            "total": total,
            "active": active,
            "pending": pending,
            "rewards": active,
            "reward_stars": active * REFERRAL_REWARD_STARS,
        }


async def get_referral_progress(user_id: int) -> tuple[int, int]:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        row = await (await conn.execute(
            "SELECT completed_dialogs, reward_claimed FROM users WHERE user_id=?",
            (user_id,),
        )).fetchone()
        return (int(row[0] or 0), int(row[1] or 0)) if row else (0, 0)


# ---------- РЕКЛАМНАЯ ПЛОЩАДКА ----------
async def create_ad_order(advertiser_id: int, campaign_type: str, target_amount: int,
                          package_size: int, package_price_stars: int, total_price_stars: int,
                          source_chat_id: int | None = None, source_message_id: int | None = None,
                          source_preview_text: str | None = None, channel_ref: str | None = None, community_type: str | None = None,
                          community_title: str | None = None, community_url: str | None = None) -> int:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        cur = await conn.execute(
            """INSERT INTO advertising_orders
            (advertiser_id,campaign_type,target_amount,package_size,package_price_stars,total_price_stars,
             source_chat_id,source_message_id,source_preview_text,channel_ref,community_type,community_title,community_url)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (advertiser_id,campaign_type,target_amount,package_size,package_price_stars,total_price_stars,
             source_chat_id,source_message_id,source_preview_text,channel_ref,community_type,community_title,community_url))
        await conn.commit()
        return cur.lastrowid

async def get_user_ad_orders(user_id: int):
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        cur = await conn.execute(
            """SELECT id,campaign_type,status,completed_amount,target_amount,total_price_stars,
                      channel_ref,community_url
               FROM advertising_orders WHERE advertiser_id=? ORDER BY id DESC LIMIT 20""", (user_id,))
        return await cur.fetchall()

async def moderate_ad_order(order_id: int, approved: bool, admin_id: int, rejection_reason: str | None = None):
    new_status = "awaiting_payment" if approved else "rejected"
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        cur = await conn.execute(
            """UPDATE advertising_orders SET status=?, moderated_by=?, rejection_reason=?
               WHERE id=? AND status='pending_moderation'
               RETURNING advertiser_id,total_price_stars""",
            (new_status, admin_id, rejection_reason if not approved else None, order_id))
        row = await cur.fetchone()
        await conn.commit()
        return row

async def activate_ad_order(order_id: int, advertiser_id: int, payment_charge_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        cur = await conn.execute(
            """UPDATE advertising_orders
               SET status='active', telegram_payment_charge_id=?, started_at=CURRENT_TIMESTAMP
               WHERE id=? AND advertiser_id=? AND status='awaiting_payment'""",
            (payment_charge_id, order_id, advertiser_id))
        await conn.commit()
        return cur.rowcount == 1

async def reserve_next_ad_campaign(user_id: int, dialog_key: str, exclude_campaign_id: int | None = None):
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        existing = await conn.execute(
            "SELECT 1 FROM advertising_impressions WHERE user_id=? AND dialog_key=?", (user_id, dialog_key))
        if await existing.fetchone():
            await conn.rollback(); return None
        sql = """SELECT id,source_chat_id,source_message_id FROM advertising_orders
                 WHERE campaign_type='post' AND status='active' AND completed_amount < target_amount
                   AND source_chat_id IS NOT NULL AND source_message_id IS NOT NULL"""
        params = []
        if exclude_campaign_id is not None:
            sql += " AND id<>?"; params.append(exclude_campaign_id)
        sql += " ORDER BY CASE WHEN last_delivery_at IS NULL THEN 0 ELSE 1 END, last_delivery_at, started_at, id LIMIT 1"
        cur = await conn.execute(sql, params)
        row = await cur.fetchone()
        if not row:
            await conn.rollback(); return None
        try:
            await conn.execute(
                "INSERT INTO advertising_impressions(campaign_id,user_id,dialog_key,status) VALUES (?,?,?,'reserved')",
                (row[0], user_id, dialog_key))
        except aiosqlite.IntegrityError:
            await conn.rollback(); return None
        await conn.commit()
        return row

async def release_ad_reservation(campaign_id: int, user_id: int, dialog_key: str):
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("DELETE FROM advertising_impressions WHERE campaign_id=? AND user_id=? AND dialog_key=? AND status='reserved'",
                           (campaign_id,user_id,dialog_key))
        await conn.commit()

async def confirm_ad_impression(campaign_id: int, user_id: int, dialog_key: str):
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        cur = await conn.execute(
            """UPDATE advertising_impressions SET status='confirmed', confirmed_at=CURRENT_TIMESTAMP
               WHERE campaign_id=? AND user_id=? AND dialog_key=? AND status='reserved'""",
            (campaign_id,user_id,dialog_key))
        if cur.rowcount != 1:
            await conn.rollback(); return False, None
        cur = await conn.execute(
            """UPDATE advertising_orders SET completed_amount=completed_amount+1,last_delivery_at=CURRENT_TIMESTAMP
               WHERE id=? AND status='active' AND completed_amount<target_amount
               RETURNING advertiser_id,completed_amount,target_amount""", (campaign_id,))
        row = await cur.fetchone()
        if not row:
            await conn.rollback(); return False, None
        completed = row[1] >= row[2]
        if completed:
            await conn.execute("UPDATE advertising_orders SET status='completed',completed_at=CURRENT_TIMESTAMP WHERE id=?", (campaign_id,))
        await conn.commit()
        return completed, row[0]

async def get_active_subscription_campaigns():
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        cur = await conn.execute(
            """SELECT id,channel_ref,community_title,community_url FROM advertising_orders
               WHERE campaign_type='subscription' AND status='active' AND completed_amount<target_amount ORDER BY started_at,id""")
        return await cur.fetchall()

async def confirm_sponsor_subscriber(campaign_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            await conn.execute("INSERT INTO sponsor_subscriptions(campaign_id,user_id) VALUES (?,?)", (campaign_id,user_id))
        except aiosqlite.IntegrityError:
            await conn.rollback(); return False
        cur = await conn.execute(
            """UPDATE advertising_orders SET completed_amount=completed_amount+1
               WHERE id=? AND status='active' AND completed_amount<target_amount
               RETURNING completed_amount,target_amount""", (campaign_id,))
        row = await cur.fetchone()
        if row and row[0] >= row[1]:
            await conn.execute("UPDATE advertising_orders SET status='completed',completed_at=CURRENT_TIMESTAMP WHERE id=?", (campaign_id,))
        await conn.commit()
        return bool(row)


async def get_admin_ad_campaigns(limit: int = 100):
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        cur = await conn.execute(
            """SELECT id,campaign_type,status,completed_amount,target_amount,community_type,community_title
               FROM advertising_orders
               ORDER BY CASE status WHEN 'active' THEN 0 WHEN 'paused' THEN 1 WHEN 'completed' THEN 2 ELSE 3 END, id DESC
               LIMIT ?""", (limit,))
        return await cur.fetchall()

async def get_admin_ad_campaign(campaign_id: int):
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        cur = await conn.execute(
            """SELECT id,advertiser_id,campaign_type,status,target_amount,completed_amount,package_size,
                      package_price_stars,total_price_stars,source_chat_id,source_message_id,channel_ref,
                      community_type,community_title,community_url,created_at,started_at,completed_at
               FROM advertising_orders WHERE id=?""", (campaign_id,))
        return await cur.fetchone()

async def set_ad_campaign_paused(campaign_id: int, paused: bool) -> bool:
    expected = 'active' if paused else 'paused'
    new_status = 'paused' if paused else 'active'
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        cur = await conn.execute(
            "UPDATE advertising_orders SET status=? WHERE id=? AND status=? AND completed_amount<target_amount",
            (new_status, campaign_id, expected))
        await conn.commit()
        return cur.rowcount == 1

async def get_ad_order_for_user(order_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        cur = await conn.execute(
            """SELECT id,campaign_type,status,target_amount,completed_amount,total_price_stars,
                      source_chat_id,source_message_id,channel_ref,community_type,community_title,community_url,
                      package_size,package_price_stars,created_at,started_at,completed_at,source_preview_text,
                      rejection_reason
               FROM advertising_orders WHERE id=? AND advertiser_id=?""", (order_id, user_id))
        return await cur.fetchone()

async def cancel_pending_ad_order(order_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        cur = await conn.execute(
            """SELECT id FROM advertising_orders
               WHERE id=? AND advertiser_id=?
                 AND status IN ('pending_moderation', 'awaiting_payment')""",
            (order_id, user_id),
        )
        if not await cur.fetchone():
            await conn.rollback()
            return False
        await conn.execute("DELETE FROM advertising_impressions WHERE campaign_id=?", (order_id,))
        await conn.execute("DELETE FROM sponsor_subscriptions WHERE campaign_id=?", (order_id,))
        await conn.execute("DELETE FROM advertising_orders WHERE id=? AND advertiser_id=?", (order_id, user_id))
        await conn.commit()
        return True

async def update_pending_ad_order_quantity(order_id: int, user_id: int, target_amount: int,
                                           package_size: int, package_price_stars: int,
                                           total_price_stars: int) -> bool:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        cur = await conn.execute(
            """UPDATE advertising_orders
               SET target_amount=?,package_size=?,package_price_stars=?,total_price_stars=?
               WHERE id=? AND advertiser_id=? AND status='pending_moderation'""",
            (target_amount, package_size, package_price_stars, total_price_stars, order_id, user_id))
        await conn.commit()
        return cur.rowcount == 1


async def get_user_ad_statistics(user_id: int):
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        cur = await conn.execute(
            """SELECT COUNT(*),
                      COALESCE(SUM(CASE WHEN campaign_type='post' THEN completed_amount ELSE 0 END), 0),
                      COALESCE(SUM(CASE WHEN campaign_type='subscription' THEN completed_amount ELSE 0 END), 0)
               FROM advertising_orders
               WHERE advertiser_id=? AND status='completed'""",
            (user_id,),
        )
        return await cur.fetchone()


async def clone_completed_ad_order(order_id: int, user_id: int, target_amount: int,
                                   package_size: int, package_price_stars: int,
                                   total_price_stars: int) -> int | None:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        cur = await conn.execute(
            """SELECT campaign_type,source_chat_id,source_message_id,source_preview_text,channel_ref,
                      community_type,community_title,community_url
               FROM advertising_orders
               WHERE id=? AND advertiser_id=? AND status='completed'""",
            (order_id, user_id),
        )
        row = await cur.fetchone()
        if not row:
            await conn.rollback()
            return None
        cur = await conn.execute(
            """INSERT INTO advertising_orders
               (advertiser_id,campaign_type,target_amount,package_size,package_price_stars,total_price_stars,
                source_chat_id,source_message_id,source_preview_text,channel_ref,community_type,community_title,community_url)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (user_id, row[0], target_amount, package_size, package_price_stars, total_price_stars,
             row[1], row[2], row[3], row[4], row[5], row[6], row[7]),
        )
        await conn.commit()
        return cur.lastrowid

async def delete_ad_campaign(campaign_id: int) -> bool:
    """Удаляет рекламную заявку и все связанные служебные записи."""
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute("SELECT 1 FROM advertising_orders WHERE id=?", (campaign_id,))
        if not await cursor.fetchone():
            return False
        await db.execute("DELETE FROM advertising_impressions WHERE campaign_id=?", (campaign_id,))
        await db.execute("DELETE FROM sponsor_subscriptions WHERE campaign_id=?", (campaign_id,))
        await db.execute("DELETE FROM advertising_orders WHERE id=?", (campaign_id,))
        await db.commit()
        return True


# ---------- ИГРА «ПОЙМАТЬ CASPER» ----------

async def get_search_game_reward_state(user_id: int) -> dict:
    """Возвращает ограничения и накопленные награды игрока."""
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        row = await (
            await db.execute(
                """
                SELECT search_game_vip_won_until,
                       search_game_discount_status,
                       search_game_discount_partner_id,
                       search_game_stars_date,
                       search_game_stars_today
                FROM users
                WHERE user_id=?
                """,
                (user_id,),
            )
        ).fetchone()

    if not row:
        return {
            "vip_won_until": None,
            "discount_status": None,
            "discount_partner_id": None,
            "stars_date": None,
            "stars_today": 0,
        }

    return {
        "vip_won_until": row[0],
        "discount_status": row[1],
        "discount_partner_id": row[2],
        "stars_date": row[3],
        "stars_today": int(row[4] or 0),
    }


async def can_win_search_game_vip(user_id: int) -> bool:
    """VIP снова участвует в розыгрыше спустя 24 часа после выигрыша."""
    state = await get_search_game_reward_state(user_id)
    won_until = state["vip_won_until"]

    if not won_until:
        return True

    try:
        return datetime.now() >= datetime.fromisoformat(won_until)
    except (TypeError, ValueError):
        return True


async def grant_search_game_vip(user_id: int) -> None:
    """Продлевает VIP на сутки и блокирует новый VIP-выигрыш на 24 часа."""
    await extend_user_vip_days(user_id, days=1)

    won_until = (datetime.now() + timedelta(days=1)).isoformat()

    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute(
            """
            UPDATE users
            SET search_game_vip_won_until=?
            WHERE user_id=?
            """,
            (won_until, user_id),
        )
        await db.commit()

    await log_action(
        user_id,
        "search_game_vip",
        f"blocked_until={won_until}",
    )


async def has_search_game_discount(user_id: int) -> bool:
    """Проверяет наличие ожидающей или активной скидки."""
    state = await get_search_game_reward_state(user_id)
    return state["discount_status"] in {"waiting", "active"}


async def grant_search_game_discount(user_id: int) -> bool:
    """Сохраняет скидку до ближайшего найденного диалога."""
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute(
            """
            UPDATE users
            SET search_game_discount_status='waiting',
                search_game_discount_partner_id=NULL
            WHERE user_id=?
              AND (
                  search_game_discount_status IS NULL
                  OR search_game_discount_status NOT IN ('waiting', 'active')
              )
            """,
            (user_id,),
        )
        await db.commit()
        granted = bool(cursor.rowcount)

    if granted:
        await log_action(user_id, "search_game_discount", "status=waiting")

    return granted


async def activate_search_game_discount(
    user_id: int,
    partner_id: int,
) -> bool:
    """Привязывает ожидающую скидку к найденному собеседнику."""
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cursor = await db.execute(
            """
            UPDATE users
            SET search_game_discount_status='active',
                search_game_discount_partner_id=?
            WHERE user_id=?
              AND search_game_discount_status='waiting'
            """,
            (partner_id, user_id),
        )
        await db.commit()
        return bool(cursor.rowcount)


async def has_active_search_game_discount(
    user_id: int,
    partner_id: int,
) -> bool:
    """Проверяет скидку пользователя в конкретном активном диалоге."""
    state = await get_search_game_reward_state(user_id)

    return (
        state["discount_status"] == "active"
        and state["discount_partner_id"] == partner_id
    )


async def clear_search_game_discount(user_id: int) -> None:
    """Сжигает скидку после завершения или смены диалога."""
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute(
            """
            UPDATE users
            SET search_game_discount_status=NULL,
                search_game_discount_partner_id=NULL
            WHERE user_id=?
            """,
            (user_id,),
        )
        await db.commit()


async def grant_search_game_star(
    user_id: int,
    amount: int = 25,
    daily_limit: int = 25,
) -> tuple[bool, int]:
    """
    Атомарно начисляет внутренние звёзды за победу в CASPER.

    Возвращает:
        (начислена ли награда, сколько звёзд выиграно сегодня)
    """
    amount = max(1, int(amount))
    daily_limit = max(amount, int(daily_limit))
    today = datetime.now().date().isoformat()

    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute("PRAGMA busy_timeout=10000")
        await db.execute("BEGIN IMMEDIATE")

        row = await (
            await db.execute(
                """
                SELECT search_game_stars_date,
                       search_game_stars_today
                FROM users
                WHERE user_id=?
                """,
                (user_id,),
            )
        ).fetchone()

        if not row:
            await db.rollback()
            return False, 0

        saved_date = row[0]
        stars_today = int(row[1] or 0)

        if saved_date != today:
            stars_today = 0

        if stars_today + amount > daily_limit:
            await db.rollback()
            return False, stars_today

        new_total = stars_today + amount

        await db.execute(
            """
            UPDATE users
            SET stars_balance=stars_balance+?,
                search_game_stars_date=?,
                search_game_stars_today=?
            WHERE user_id=?
            """,
            (amount, today, new_total, user_id),
        )

        await db.execute(
            """
            INSERT INTO logs(user_id, action, details, timestamp)
            VALUES (?, 'search_game_star', ?, ?)
            """,
            (
                user_id,
                (
                    f"amount={amount};"
                    f"today={new_total};"
                    f"limit={daily_limit}"
                ),
                datetime.now().isoformat(),
            ),
        )

        await db.commit()
        return True, new_total



# ---------- АНОНИМНЫЕ ВОПРОСЫ ----------
async def _generate_question_token(db: aiosqlite.Connection) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        token = ''.join(secrets.choice(alphabet) for _ in range(10))
        row = await (await db.execute(
            "SELECT 1 FROM users WHERE question_token=?", (token,)
        )).fetchone()
        if not row:
            return token


async def get_or_create_question_token(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        row = await (await db.execute(
            "SELECT question_token FROM users WHERE user_id=?", (user_id,)
        )).fetchone()
        if row and row[0]:
            return str(row[0])
        token = await _generate_question_token(db)
        await db.execute(
            "UPDATE users SET question_token=? WHERE user_id=?", (token, user_id)
        )
        await db.commit()
        return token


async def get_question_owner_by_token(token: str):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        return await (await db.execute(
            "SELECT user_id, username, first_name, last_name, questions_enabled "
            "FROM users WHERE question_token=?", (token,)
        )).fetchone()


async def get_question_owner_by_id(user_id: int):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        return await (await db.execute(
            "SELECT user_id, username, first_name, last_name, questions_enabled "
            "FROM users WHERE user_id=?", (user_id,)
        )).fetchone()


async def record_question_link_visit(owner_id: int, visitor_id: int) -> None:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute(
            "INSERT INTO question_link_visits(owner_id, visitor_id) VALUES (?,?)",
            (owner_id, visitor_id),
        )
        await db.commit()


async def create_anonymous_question(sender_id: int, receiver_id: int, text: str) -> str:
    public_id = secrets.token_urlsafe(9).replace('-', '').replace('_', '')[:12]
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute(
            "INSERT INTO anonymous_questions(public_id,sender_id,receiver_id,text) "
            "VALUES (?,?,?,?)",
            (public_id, sender_id, receiver_id, text),
        )
        await db.commit()
    return public_id


async def get_question_by_public_id(public_id: str):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        return await (await db.execute(
            "SELECT id,public_id,sender_id,receiver_id,text,status,answer_text,created_at,"
            "read_at,answered_at,author_revealed FROM anonymous_questions WHERE public_id=?",
            (public_id,),
        )).fetchone()


async def get_user_questions(user_id: int, limit: int = 20, offset: int = 0):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        return await (await db.execute(
            "SELECT id,public_id,status,created_at FROM anonymous_questions "
            "WHERE receiver_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        )).fetchall()


async def count_user_questions(user_id: int) -> tuple[int, int]:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        row = await (await db.execute(
            "SELECT COUNT(*), SUM(CASE WHEN status='new' THEN 1 ELSE 0 END) "
            "FROM anonymous_questions WHERE receiver_id=?", (user_id,)
        )).fetchone()
        return int(row[0] or 0), int(row[1] or 0)


async def mark_question_read(public_id: str, receiver_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cur = await db.execute(
            "UPDATE anonymous_questions SET status=CASE WHEN status='new' THEN 'read' ELSE status END, "
            "read_at=COALESCE(read_at,CURRENT_TIMESTAMP) WHERE public_id=? AND receiver_id=?",
            (public_id, receiver_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def answer_question(public_id: str, receiver_id: int, answer_text: str):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        row = await (await db.execute(
            "SELECT sender_id,text FROM anonymous_questions WHERE public_id=? AND receiver_id=?",
            (public_id, receiver_id),
        )).fetchone()
        if not row:
            return None
        await db.execute(
            "UPDATE anonymous_questions SET status='answered',answer_text=?,answered_at=CURRENT_TIMESTAMP "
            "WHERE public_id=? AND receiver_id=?",
            (answer_text, public_id, receiver_id),
        )
        await db.commit()
        return row


async def get_question_user_stats(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        visits = await (await db.execute(
            "SELECT COUNT(*), COUNT(DISTINCT visitor_id) FROM question_link_visits WHERE owner_id=?",
            (user_id,),
        )).fetchone()
        qs = await (await db.execute(
            "SELECT COUNT(*), SUM(CASE WHEN status='answered' THEN 1 ELSE 0 END), "
            "SUM(author_revealed) FROM anonymous_questions WHERE receiver_id=?",
            (user_id,),
        )).fetchone()
        purchases = await (await db.execute(
            "SELECT "
            "SUM(CASE WHEN type='question_gift' THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN type='question_vip' THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN type='question_stars' THEN price_stars ELSE 0 END), "
            "SUM(CASE WHEN type='question_premium' THEN 1 ELSE 0 END) "
            "FROM purchases WHERE receiver_id=?",
            (user_id,),
        )).fetchone()
        return {
            'visits': int(visits[0] or 0),
            'unique_visits': int(visits[1] or 0),
            'questions': int(qs[0] or 0),
            'answers': int(qs[1] or 0),
            'reveals': int(qs[2] or 0),
            'gifts': int(purchases[0] or 0),
            'vip': int(purchases[1] or 0),
            'stars': int(purchases[2] or 0),
            'premium': int(purchases[3] or 0),
        }


async def set_question_chat_pending(public_id: str, pending: bool = True) -> None:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute(
            "UPDATE anonymous_questions SET question_chat_pending=? WHERE public_id=?",
            (1 if pending else 0, public_id),
        )
        await db.commit()


async def set_answer_chat_pending(public_id: str, pending: bool = True) -> None:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute(
            "UPDATE anonymous_questions SET answer_chat_pending=? WHERE public_id=?",
            (1 if pending else 0, public_id),
        )
        await db.commit()


async def consume_pending_question_activity(user_id: int) -> tuple[int, int]:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        q_row = await (await db.execute(
            "SELECT COUNT(*) FROM anonymous_questions "
            "WHERE receiver_id=? AND question_chat_pending=1",
            (user_id,),
        )).fetchone()
        a_row = await (await db.execute(
            "SELECT COUNT(*) FROM anonymous_questions "
            "WHERE sender_id=? AND answer_chat_pending=1",
            (user_id,),
        )).fetchone()
        await db.execute(
            "UPDATE anonymous_questions SET question_chat_pending=0 "
            "WHERE receiver_id=? AND question_chat_pending=1",
            (user_id,),
        )
        await db.execute(
            "UPDATE anonymous_questions SET answer_chat_pending=0 "
            "WHERE sender_id=? AND answer_chat_pending=1",
            (user_id,),
        )
        await db.commit()
        return int(q_row[0] or 0), int(a_row[0] or 0)


async def get_user_question_answers(user_id: int, limit: int = 20, offset: int = 0):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        return await (await db.execute(
            "SELECT id,public_id,answered_at,answer_read_at FROM anonymous_questions "
            "WHERE sender_id=? AND answer_text IS NOT NULL "
            "ORDER BY answered_at DESC, id DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        )).fetchall()


async def count_user_question_answers(user_id: int) -> tuple[int, int]:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        row = await (await db.execute(
            "SELECT COUNT(*), SUM(CASE WHEN answer_read_at IS NULL THEN 1 ELSE 0 END) "
            "FROM anonymous_questions WHERE sender_id=? AND answer_text IS NOT NULL",
            (user_id,),
        )).fetchone()
        return int(row[0] or 0), int(row[1] or 0)


async def mark_question_answer_read(public_id: str, sender_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        cur = await db.execute(
            "UPDATE anonymous_questions SET answer_read_at=COALESCE(answer_read_at,CURRENT_TIMESTAMP) "
            "WHERE public_id=? AND sender_id=? AND answer_text IS NOT NULL",
            (public_id, sender_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def get_users_without_questions_intro(limit: int = 500, offset: int = 0):
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        return await (await db.execute(
            "SELECT user_id FROM users WHERE COALESCE(questions_intro_sent,0)=0 "
            "ORDER BY user_id LIMIT ? OFFSET ?",
            (limit, offset),
        )).fetchall()


async def mark_questions_intro_sent(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await db.execute(
            "UPDATE users SET questions_intro_sent=1 WHERE user_id=?",
            (user_id,),
        )
        await db.commit()
