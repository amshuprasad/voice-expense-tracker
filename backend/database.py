import sqlite3
from contextlib import contextmanager

DB_PATH = "expenses.db"


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_text TEXT,
                amount REAL,
                category TEXT,
                description TEXT,
                date TEXT,
                people TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def insert_expense(expense: dict) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO expenses (raw_text, amount, category, description, date, people)
            VALUES (:raw_text, :amount, :category, :description, :date, :people)
            """,
            expense,
        )
        conn.commit()
        return cur.lastrowid


def list_expenses(limit: int = 100):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM expenses ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]


def delete_expense(expense_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()


def summary_by_category():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT category, SUM(amount) as total, COUNT(*) as count "
            "FROM expenses GROUP BY category ORDER BY total DESC"
        ).fetchall()
        return [dict(row) for row in rows]
