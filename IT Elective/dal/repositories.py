from __future__ import annotations

import json
import sqlite3
from datetime import date
from typing import Iterable, List, Optional, Sequence, Tuple

from dto.models import CategoryDTO, PurchaseDTO, UserDTO
from utils.error_logger import log_error


class DalError(Exception):
    pass


class UserRepository:
    def __init__(self, con: sqlite3.Connection):
        self._con = con

    def get_by_username(self, username: str) -> Optional[sqlite3.Row]:
        try:
            return self._con.execute(
                "SELECT id, username, password_hash, display_name FROM users WHERE username=?",
                (username.strip().lower(),),
            ).fetchone()
        except sqlite3.Error as e:
            log_error("DAL.UserRepository.get_by_username", str(e))
            raise DalError(str(e)) from e

    def get_dto_by_id(self, user_id: int) -> Optional[UserDTO]:
        try:
            row = self._con.execute(
                "SELECT id, username, display_name FROM users WHERE id=?",
                (int(user_id),),
            ).fetchone()
            if not row:
                return None
            return UserDTO(id=int(row["id"]), username=row["username"], display_name=row["display_name"])
        except sqlite3.Error as e:
            log_error("DAL.UserRepository.get_dto_by_id", str(e))
            raise DalError(str(e)) from e

    def create(self, username: str, password_hash: bytes, display_name: str) -> int:
        try:
            cur = self._con.execute(
                "INSERT INTO users(username, password_hash, display_name) VALUES (?,?,?)",
                (username.strip().lower(), password_hash, display_name.strip()),
            )
            self._con.commit()
            return int(cur.lastrowid)
        except sqlite3.IntegrityError as e:
            log_error("DAL.UserRepository.create", str(e))
            raise DalError("Username already exists.") from e
        except sqlite3.Error as e:
            log_error("DAL.UserRepository.create", str(e))
            raise DalError(str(e)) from e


class CategoryRepository:
    def __init__(self, con: sqlite3.Connection):
        self._con = con

    def list_all(self) -> List[CategoryDTO]:
        try:
            rows = self._con.execute("SELECT id, name FROM categories ORDER BY name").fetchall()
            return [CategoryDTO(id=int(r["id"]), name=r["name"]) for r in rows]
        except sqlite3.Error as e:
            log_error("DAL.CategoryRepository.list_all", str(e))
            raise DalError(str(e)) from e

    def get_by_id(self, category_id: int) -> Optional[CategoryDTO]:
        try:
            r = self._con.execute("SELECT id, name FROM categories WHERE id=?", (int(category_id),)).fetchone()
            if not r:
                return None
            return CategoryDTO(id=int(r["id"]), name=r["name"])
        except sqlite3.Error as e:
            log_error("DAL.CategoryRepository.get_by_id", str(e))
            raise DalError(str(e)) from e

    def get_or_create(self, name: str) -> CategoryDTO:
        try:
            name = name.strip()
            row = self._con.execute("SELECT id, name FROM categories WHERE name=?", (name,)).fetchone()
            if row:
                return CategoryDTO(id=int(row["id"]), name=row["name"])
            cur = self._con.execute("INSERT INTO categories(name) VALUES (?)", (name,))
            self._con.commit()
            return CategoryDTO(id=int(cur.lastrowid), name=name)
        except sqlite3.Error as e:
            log_error("DAL.CategoryRepository.get_or_create", str(e))
            raise DalError(str(e)) from e


class PurchaseRepository:
    def __init__(self, con: sqlite3.Connection):
        self._con = con

    def list_for_user(self, user_id: int) -> List[PurchaseDTO]:
        try:
            rows = self._con.execute(
                """
                SELECT p.id, p.user_id, p.item_name, p.category_id, c.name AS category_name,
                       p.price, p.purchased_on, p.is_eco_friendly, p.eco_tags_json
                FROM purchases p
                JOIN categories c ON c.id = p.category_id
                WHERE p.user_id=?
                ORDER BY p.purchased_on DESC, p.id DESC
                """,
                (int(user_id),),
            ).fetchall()
            return [self._row_to_dto(r) for r in rows]
        except sqlite3.Error as e:
            log_error("DAL.PurchaseRepository.list_for_user", str(e))
            raise DalError(str(e)) from e

    def get_for_user(self, user_id: int, purchase_id: int) -> Optional[PurchaseDTO]:
        try:
            r = self._con.execute(
                """
                SELECT p.id, p.user_id, p.item_name, p.category_id, c.name AS category_name,
                       p.price, p.purchased_on, p.is_eco_friendly, p.eco_tags_json
                FROM purchases p
                JOIN categories c ON c.id = p.category_id
                WHERE p.user_id=? AND p.id=?
                """,
                (int(user_id), int(purchase_id)),
            ).fetchone()
            return self._row_to_dto(r) if r else None
        except sqlite3.Error as e:
            log_error("DAL.PurchaseRepository.get_for_user", str(e))
            raise DalError(str(e)) from e

    def create(
        self,
        *,
        user_id: int,
        item_name: str,
        category_id: int,
        price: float,
        purchased_on: date,
        is_eco_friendly: bool,
        eco_tags: Sequence[str],
    ) -> int:
        try:
            cur = self._con.execute(
                """
                INSERT INTO purchases(user_id, category_id, item_name, price, purchased_on, is_eco_friendly, eco_tags_json)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    int(user_id),
                    int(category_id),
                    item_name.strip(),
                    float(price),
                    purchased_on.isoformat(),
                    1 if is_eco_friendly else 0,
                    json.dumps(list(eco_tags), ensure_ascii=False),
                ),
            )
            self._con.commit()
            return int(cur.lastrowid)
        except sqlite3.Error as e:
            log_error("DAL.PurchaseRepository.create", str(e))
            raise DalError(str(e)) from e

    def update(
        self,
        *,
        user_id: int,
        purchase_id: int,
        item_name: str,
        category_id: int,
        price: float,
        purchased_on: date,
        is_eco_friendly: bool,
        eco_tags: Sequence[str],
    ) -> None:
        try:
            self._con.execute(
                """
                UPDATE purchases
                SET item_name=?, category_id=?, price=?, purchased_on=?, is_eco_friendly=?, eco_tags_json=?
                WHERE id=? AND user_id=?
                """,
                (
                    item_name.strip(),
                    int(category_id),
                    float(price),
                    purchased_on.isoformat(),
                    1 if is_eco_friendly else 0,
                    json.dumps(list(eco_tags), ensure_ascii=False),
                    int(purchase_id),
                    int(user_id),
                ),
            )
            self._con.commit()
        except sqlite3.Error as e:
            log_error("DAL.PurchaseRepository.update", str(e))
            raise DalError(str(e)) from e

    def delete(self, *, user_id: int, purchase_id: int) -> None:
        try:
            self._con.execute("DELETE FROM purchases WHERE id=? AND user_id=?", (int(purchase_id), int(user_id)))
            self._con.commit()
        except sqlite3.Error as e:
            log_error("DAL.PurchaseRepository.delete", str(e))
            raise DalError(str(e)) from e

    @staticmethod
    def _row_to_dto(r: sqlite3.Row) -> PurchaseDTO:
        eco_tags = json.loads(r["eco_tags_json"] or "[]")
        return PurchaseDTO(
            id=int(r["id"]),
            user_id=int(r["user_id"]),
            item_name=r["item_name"],
            category_id=int(r["category_id"]),
            category_name=r["category_name"],
            price=float(r["price"]),
            purchased_on=date.fromisoformat(r["purchased_on"]),
            is_eco_friendly=bool(int(r["is_eco_friendly"])),
            eco_tags=eco_tags,
        )

