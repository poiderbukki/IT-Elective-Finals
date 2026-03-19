from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from utils.error_logger import log_error

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  password_hash BLOB NOT NULL,
  display_name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS purchases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  category_id INTEGER NOT NULL,
  item_name TEXT NOT NULL,
  price REAL NOT NULL,
  purchased_on TEXT NOT NULL,
  is_eco_friendly INTEGER NOT NULL CHECK (is_eco_friendly IN (0,1)),
  eco_tags_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_purchases_user_date ON purchases(user_id, purchased_on);
"""


@dataclass(frozen=True)
class DbConfig:
    db_path: Path


def connect(cfg: DbConfig) -> sqlite3.Connection:
    con = sqlite3.connect(str(cfg.db_path), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def init_db(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA_SQL)
    con.commit()


def _table_is_empty(con: sqlite3.Connection, table: str) -> bool:
    cur = con.execute(f"SELECT COUNT(*) AS c FROM {table}")
    return int(cur.fetchone()["c"]) == 0


def seed_from_json(
    con: sqlite3.Connection,
    seed_file: Path,
    *,
    password_hasher,
    allow_reseed: bool = False,
) -> None:
    """
    Seeds initial data. If allow_reseed=False, only seeds when tables are empty.
    password_hasher: callable(plain_password:str)->bytes
    """
    if not seed_file.exists():
        return

    if not allow_reseed:
        if not (_table_is_empty(con, "users") and _table_is_empty(con, "categories")):
            return

    data = json.loads(seed_file.read_text(encoding="utf-8"))

    users = data.get("users", [])
    categories = data.get("categories", [])
    purchases = data.get("purchases", [])

    try:
        with con:
            for c in categories:
                con.execute("INSERT OR IGNORE INTO categories(name) VALUES (?)", (c["name"].strip(),))

            for u in users:
                pw_hash = password_hasher(u["password"])
                con.execute(
                    "INSERT OR IGNORE INTO users(username, password_hash, display_name) VALUES (?,?,?)",
                    (u["username"].strip().lower(), pw_hash, u.get("display_name", u["username"]).strip()),
                )

            # Purchases reference usernames + category names in seed
            for p in purchases:
                username = p["username"].strip().lower()
                cat_name = p["category"].strip()
                user_row = con.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
                cat_row = con.execute("SELECT id FROM categories WHERE name=?", (cat_name,)).fetchone()
                if not user_row or not cat_row:
                    continue

                eco_tags_json = json.dumps(p.get("eco_tags", []), ensure_ascii=False)
                con.execute(
                    """
                    INSERT INTO purchases(
                      user_id, category_id, item_name, price, purchased_on, is_eco_friendly, eco_tags_json
                    ) VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        int(user_row["id"]),
                        int(cat_row["id"]),
                        p["item_name"].strip(),
                        float(p["price"]),
                        p["purchased_on"],
                        1 if bool(p["is_eco_friendly"]) else 0,
                        eco_tags_json,
                    ),
                )
    except sqlite3.Error:
        # NFR3: all db ops are try/except; swallow seed errors (prototype)
        log_error("DAL.seed_from_json", "Failed to seed data from seed.json")
        return

