from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional, Sequence

from dal.backup_restore import (
    BackupRestoreError,
    export_user_data_to_json,
    import_user_data_from_json,
)
from dal.repositories import CategoryRepository, DalError, PurchaseRepository, UserRepository
from dto.models import (
    CategoryDTO,
    MonthlySummaryDTO,
    NewPurchaseDTO,
    PurchaseDTO,
    ScoreResultDTO,
    UpdatePurchaseDTO,
    UserDTO,
)

from .auth import AuthError, hash_password, verify_password
from .scoring import compute_scores


class BllError(ValueError):
    pass


class AuthService:
    def __init__(self, user_repo: UserRepository):
        self._users = user_repo

    def login(self, username: str, password: str) -> UserDTO:
        username = (username or "").strip().lower()
        password = password or ""
        if not username:
            raise BllError("Username is required.")
        if not password:
            raise BllError("Password is required.")

        try:
            row = self._users.get_by_username(username)
        except DalError as e:
            raise BllError("Database error while logging in.") from e

        if not row:
            raise BllError("Invalid username or password.")
        if not verify_password(password, row["password_hash"]):
            raise BllError("Invalid username or password.")

        return UserDTO(id=int(row["id"]), username=row["username"], display_name=row["display_name"])

    def register(self, username: str, password: str, display_name: str) -> UserDTO:
        username = (username or "").strip().lower()
        display_name = (display_name or "").strip()
        if not username:
            raise BllError("Username is required.")
        if len(username) < 3:
            raise BllError("Username must be at least 3 characters.")
        if not display_name:
            display_name = username
        try:
            pw_hash = hash_password(password)
        except AuthError as e:
            raise BllError(str(e)) from e

        try:
            user_id = self._users.create(username, pw_hash, display_name)
            return UserDTO(id=user_id, username=username, display_name=display_name)
        except DalError as e:
            raise BllError(str(e)) from e


class CatalogService:
    def __init__(self, cat_repo: CategoryRepository):
        self._cats = cat_repo

    def list_categories(self) -> List[CategoryDTO]:
        try:
            return self._cats.list_all()
        except DalError as e:
            raise BllError("Could not load categories.") from e


class PurchaseService:
    def __init__(self, purchase_repo: PurchaseRepository, cat_repo: CategoryRepository):
        self._p = purchase_repo
        self._cats = cat_repo

    def list_purchases(self, user_id: int) -> List[PurchaseDTO]:
        try:
            return self._p.list_for_user(user_id)
        except DalError as e:
            raise BllError("Could not load purchases.") from e

    def add_purchase(self, user_id: int, dto: NewPurchaseDTO) -> int:
        self._validate_purchase_fields(dto.item_name, dto.price, dto.purchased_on, dto.eco_tags)
        self._validate_category(dto.category_id)
        is_eco = self.classify_eco_friendly(dto.criteria_met, dto.is_eco_friendly)
        try:
            return self._p.create(
                user_id=user_id,
                item_name=dto.item_name,
                category_id=dto.category_id,
                price=dto.price,
                purchased_on=dto.purchased_on,
                is_eco_friendly=is_eco,
                eco_tags=list(dto.eco_tags) + [f"criteria:{c}" for c in dto.criteria_met],
            )
        except DalError as e:
            raise BllError("Could not save purchase.") from e

    def update_purchase(self, user_id: int, dto: UpdatePurchaseDTO) -> None:
        self._validate_purchase_fields(dto.item_name, dto.price, dto.purchased_on, dto.eco_tags)
        self._validate_category(dto.category_id)
        is_eco = self.classify_eco_friendly(dto.criteria_met, dto.is_eco_friendly)
        try:
            self._p.update(
                user_id=user_id,
                purchase_id=dto.id,
                item_name=dto.item_name,
                category_id=dto.category_id,
                price=dto.price,
                purchased_on=dto.purchased_on,
                is_eco_friendly=is_eco,
                eco_tags=list(dto.eco_tags) + [f"criteria:{c}" for c in dto.criteria_met],
            )
        except DalError as e:
            raise BllError("Could not update purchase.") from e

    def delete_purchase(self, user_id: int, purchase_id: int) -> None:
        if int(purchase_id) <= 0:
            raise BllError("Invalid purchase selected.")
        try:
            self._p.delete(user_id=user_id, purchase_id=purchase_id)
        except DalError as e:
            raise BllError("Could not delete purchase.") from e

    async def compute_score_async(self, user_id: int) -> ScoreResultDTO:
        purchases = self.list_purchases(user_id)
        # Avoid UI freeze: compute in a worker thread (prototype)
        return await asyncio.to_thread(compute_scores, purchases)

    def monthly_summaries(self, user_id: int) -> List[MonthlySummaryDTO]:
        purchases = self.list_purchases(user_id)
        buckets: dict[tuple[int, int], list[PurchaseDTO]] = {}
        for p in purchases:
            key = (p.purchased_on.year, p.purchased_on.month)
            buckets.setdefault(key, []).append(p)

        result: List[MonthlySummaryDTO] = []
        for (y, m), ps in sorted(buckets.items()):
            total = len(ps)
            eco = sum(1 for x in ps if x.is_eco_friendly)
            eco_pct = (eco / total) * 100.0 if total else 0.0
            score = compute_scores(ps).sustainability_score
            result.append(
                MonthlySummaryDTO(
                    year=y,
                    month=m,
                    total_purchases=total,
                    eco_purchases=eco,
                    eco_percentage=round(eco_pct, 2),
                    sustainability_score=round(score, 2),
                )
            )
        return result

    @staticmethod
    def classify_eco_friendly(criteria_met: Sequence[str], fallback_checkbox: bool) -> bool:
        # Paper rule: majority of sustainability criteria => eco-friendly.
        criteria_count = len([c for c in criteria_met if c])
        if criteria_count == 0:
            return bool(fallback_checkbox)
        return criteria_count >= 3

    def _validate_category(self, category_id: int) -> None:
        try:
            cat = self._cats.get_by_id(int(category_id))
        except DalError as e:
            raise BllError("Could not validate category.") from e
        if not cat:
            raise BllError("Please select a valid category.")

    @staticmethod
    def _validate_purchase_fields(item_name: str, price: float, purchased_on: date, eco_tags: Sequence[str]) -> None:
        item_name = (item_name or "").strip()
        if not item_name:
            raise BllError("Item name is required.")
        if len(item_name) > 100:
            raise BllError("Item name is too long (max 100 characters).")
        try:
            price = float(price)
        except Exception as e:
            raise BllError("Price must be a number.") from e
        if price < 0:
            raise BllError("Price cannot be negative.")
        if purchased_on > date.today():
            raise BllError("Purchase date cannot be in the future.")
        if len(list(eco_tags)) > 12:
            raise BllError("Too many eco tags (max 12).")


class BackupRestoreService:
    def __init__(self, con):
        self._con = con

    def export_backup(self, user_id: int, out_path: Path) -> Path:
        try:
            return export_user_data_to_json(self._con, user_id, out_path)
        except BackupRestoreError as e:
            raise BllError(str(e)) from e

    def restore_backup(self, user_id: int, in_path: Path) -> int:
        try:
            return import_user_data_from_json(self._con, user_id, in_path)
        except BackupRestoreError as e:
            raise BllError(str(e)) from e

