from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from dto.models import PurchaseDTO, ScoreResultDTO


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def compute_scores(purchases: Sequence[PurchaseDTO]) -> ScoreResultDTO:
    """
    SDG 12 (Responsible Consumption & Production) prototype scoring.

    Inputs are purchases with a boolean 'is_eco_friendly' plus optional tags.
    Produces:
      - eco_percentage: % eco-friendly purchases
      - sustainability_score: 0..100 composite
      - carbon_footprint_score: 0..100 (higher is better)
      - waste_reduction_score: 0..100 (higher is better)
      - risk_rating: 0..100 (higher means riskier habits)
    """
    n = len(purchases)
    if n == 0:
        return ScoreResultDTO(
            sustainability_score=0.0,
            eco_percentage=0.0,
            carbon_footprint_score=0.0,
            waste_reduction_score=0.0,
            risk_rating=0.0,
            notes="No purchases yet. Add purchases to compute your SDG 12 score.",
        )

    eco_count = sum(1 for p in purchases if p.is_eco_friendly)
    eco_percentage = (eco_count / n) * 100.0

    # Paper-aligned core algorithm:
    # sustainability score is the percentage of eco-friendly purchases.
    sustainability_score = _clamp(eco_percentage, 0.0, 100.0)

    # Additional supporting indicators (kept for dashboard richness).
    carbon_footprint_score = _clamp(eco_percentage, 0.0, 100.0)
    waste_reduction_score = _clamp(eco_percentage, 0.0, 100.0)
    risk_rating = _clamp(100.0 - sustainability_score, 0.0, 100.0)

    notes = None
    if eco_percentage < 30:
        notes = "Consider switching a few recurring items to eco-friendly alternatives to improve your SDG 12 score."
    elif eco_percentage < 60:
        notes = "Good progress—try prioritizing reusable and plastic-free options for bigger gains."
    else:
        notes = "Great habits—keep tracking and aim for consistency month to month."

    return ScoreResultDTO(
        sustainability_score=float(round(sustainability_score, 2)),
        eco_percentage=float(round(eco_percentage, 2)),
        carbon_footprint_score=float(round(carbon_footprint_score, 2)),
        waste_reduction_score=float(round(waste_reduction_score, 2)),
        risk_rating=float(round(risk_rating, 2)),
        notes=notes,
    )


BIG_O_COMPLEXITY_NOTE = """
Big O Complexity (for SDAD):
- compute_scores iterates purchases once and does O(1) work per purchase (tag normalization uses a small set).
- Time: O(n)
- Space: O(1) extra space (excluding input list), since only counters are stored.
"""

