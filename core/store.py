"""SQLite persistence: the memory that lets Sahayak coach across sessions."""
from __future__ import annotations

import os
import sqlite3
import time
from contextlib import contextmanager

DB_PATH = os.environ.get("SAHAYAK_DB", os.path.join(os.path.dirname(__file__), "..", "sahayak.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    user_id TEXT PRIMARY KEY,
    monthly_income REAL,
    monthly_expenses REAL,
    updated_at REAL
);
CREATE TABLE IF NOT EXISTS loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    lender_label TEXT NOT NULL,
    principal REAL NOT NULL,
    annual_rate REAL NOT NULL,
    term_months INTEGER NOT NULL,
    fees REAL NOT NULL DEFAULT 0,
    rate_type TEXT NOT NULL,
    emi REAL NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS repayments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_id INTEGER NOT NULL REFERENCES loans(id),
    amount REAL NOT NULL,
    paid_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS lessons (
    user_id TEXT NOT NULL,
    lesson_id TEXT NOT NULL,
    completed_at REAL NOT NULL,
    PRIMARY KEY (user_id, lesson_id)
);
"""


@contextmanager
def _conn(path: str | None = None):
    con = sqlite3.connect(path or DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def save_profile(user_id: str, monthly_income: float, monthly_expenses: float, path: str | None = None) -> None:
    with _conn(path) as c:
        c.execute(
            "INSERT INTO profile VALUES (?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET "
            "monthly_income=excluded.monthly_income, monthly_expenses=excluded.monthly_expenses, "
            "updated_at=excluded.updated_at",
            (user_id, monthly_income, monthly_expenses, time.time()),
        )


def get_profile(user_id: str, path: str | None = None) -> dict | None:
    with _conn(path) as c:
        row = c.execute("SELECT * FROM profile WHERE user_id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def add_loan(user_id: str, lender_label: str, principal: float, annual_rate: float, term_months: int,
             fees: float, rate_type: str, emi: float, path: str | None = None) -> int:
    with _conn(path) as c:
        cur = c.execute(
            "INSERT INTO loans (user_id, lender_label, principal, annual_rate, term_months, fees, rate_type, emi, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (user_id, lender_label, principal, annual_rate, term_months, fees, rate_type, emi, time.time()),
        )
        return int(cur.lastrowid)


def list_loans(user_id: str, path: str | None = None) -> list[dict]:
    with _conn(path) as c:
        rows = c.execute(
            "SELECT l.*, COALESCE(SUM(r.amount),0) AS paid FROM loans l "
            "LEFT JOIN repayments r ON r.loan_id=l.id WHERE l.user_id=? GROUP BY l.id ORDER BY l.id",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def log_repayment(user_id: str, loan_id: int, amount: float, path: str | None = None) -> None:
    with _conn(path) as c:
        owner = c.execute("SELECT user_id FROM loans WHERE id=?", (loan_id,)).fetchone()
        if owner is None or owner["user_id"] != user_id:
            raise ValueError(f"No loan {loan_id} for this user")
        c.execute("INSERT INTO repayments (loan_id, amount, paid_at) VALUES (?,?,?)", (loan_id, amount, time.time()))


def complete_lesson(user_id: str, lesson_id: str, path: str | None = None) -> None:
    with _conn(path) as c:
        c.execute("INSERT OR IGNORE INTO lessons VALUES (?,?,?)", (user_id, lesson_id, time.time()))


def completed_lessons(user_id: str, path: str | None = None) -> set[str]:
    with _conn(path) as c:
        return {r["lesson_id"] for r in c.execute("SELECT lesson_id FROM lessons WHERE user_id=?", (user_id,))}
