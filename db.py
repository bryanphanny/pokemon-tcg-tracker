import sqlite3
from datetime import datetime

DB_PATH = "bot.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets you access columns by name, not just index
    return conn


def initialize():
    """Create tables if they don't exist. Safe to call every startup."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                tcin          TEXT PRIMARY KEY,
                name          TEXT,
                url           TEXT,
                price         TEXT,
                last_status   TEXT,
                last_checked  TEXT,
                first_seen    TEXT
            )
        """)
        conn.commit()


def get_all_tcins() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute("SELECT tcin FROM products").fetchall()
        return [row["tcin"] for row in rows]


def is_known(tcin: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT 1 FROM products WHERE tcin = ?", (tcin,)).fetchone()
        return row is not None


def upsert_product(tcin: str, name: str, url: str, price: str, status: str):
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT first_seen FROM products WHERE tcin = ?", (tcin,)
        ).fetchone()

        first_seen = existing["first_seen"] if existing else now

        conn.execute("""
            INSERT INTO products (tcin, name, url, price, last_status, last_checked, first_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tcin) DO UPDATE SET
                name         = excluded.name,
                url          = excluded.url,
                price        = excluded.price,
                last_status  = excluded.last_status,
                last_checked = excluded.last_checked
        """, (tcin, name, url, price, status, now, first_seen))
        conn.commit()


def get_last_status(tcin: str) -> str | None:
    with get_connection() as conn:
        row = conn.execute("SELECT last_status FROM products WHERE tcin = ?", (tcin,)).fetchone()
        return row["last_status"] if row else None


def get_name(tcin: str) -> str | None:
    with get_connection() as conn:
        row = conn.execute("SELECT name FROM products WHERE tcin = ?", (tcin,)).fetchone()
        return row["name"] if row else None


def get_price(tcin: str) -> str | None:
    with get_connection() as conn:
        row = conn.execute("SELECT price FROM products WHERE tcin = ?", (tcin,)).fetchone()
        return row["price"] if row else None
