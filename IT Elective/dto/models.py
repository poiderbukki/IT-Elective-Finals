from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence


@dataclass(frozen=True)
class UserDTO:
    id: int
    username: str
    display_name: str


@dataclass(frozen=True)
class CategoryDTO:
    id: int
    name: str


@dataclass(frozen=True)
class PurchaseDTO:
    id: int
    user_id: int
    item_name: str
    category_id: int
    category_name: str
    price: float
    purchased_on: date
    is_eco_friendly: bool
    eco_tags: Sequence[str]


@dataclass(frozen=True)
class NewPurchaseDTO:
    item_name: str
    category_id: int
    price: float
    purchased_on: date
    is_eco_friendly: bool
    eco_tags: Sequence[str]
    criteria_met: Sequence[str]


@dataclass(frozen=True)
class UpdatePurchaseDTO:
    id: int
    item_name: str
    category_id: int
    price: float
    purchased_on: date
    is_eco_friendly: bool
    eco_tags: Sequence[str]
    criteria_met: Sequence[str]


@dataclass(frozen=True)
class MonthlySummaryDTO:
    year: int
    month: int
    total_purchases: int
    eco_purchases: int
    eco_percentage: float
    sustainability_score: float


@dataclass(frozen=True)
class ScoreResultDTO:
    sustainability_score: float
    eco_percentage: float
    carbon_footprint_score: float
    waste_reduction_score: float
    risk_rating: float
    notes: Optional[str] = None

