from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from utils.error_logger import log_error


class BackupRestoreError(Exception):
    pass


def export_user_data_to_json(con: sqlite3.Connection, user_id: int, out_path: Path) -> Path:
    try:
        user = con.execute(
            "SELECT id, username, display_name, created_at FROM users WHERE id=?",
            (int(user_id),),
        ).fetchone()
        if not user:
            raise BackupRestoreError("User not found.")

        categories = con.execute("SELECT id, name FROM categories ORDER BY name").fetchall()
        purchases = con.execute(
            """
            SELECT id, user_id, category_id, item_name, price, purchased_on, is_eco_friendly, eco_tags_json, created_at
            FROM purchases WHERE user_id=?
            ORDER BY purchased_on ASC, id ASC
            """,
            (int(user_id),),
        ).fetchall()

        payload: Dict[str, Any] = {
            "user": dict(user),
            "categories": [dict(x) for x in categories],
            "purchases": [dict(x) for x in purchases],
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return out_path
    except BackupRestoreError:
        raise
    except Exception as e:
        log_error("DAL.export_user_data_to_json", str(e))
        raise BackupRestoreError("Could not export data.") from e


def import_user_data_from_json(con: sqlite3.Connection, user_id: int, in_path: Path) -> int:
    """
    Restores purchases for a user from an export file.
    Current strategy: append imported rows (does not delete existing rows).
    Returns number of inserted purchases.
    """
    try:
        if not in_path.exists():
            raise BackupRestoreError("Backup file not found.")
        payload = json.loads(in_path.read_text(encoding="utf-8"))
        categories = payload.get("categories", [])
        purchases = payload.get("purchases", [])

        with con:
            # Ensure categories exist
            id_map: dict[int, int] = {}
            for c in categories:
                name = (c.get("name") or "").strip()
                if not name:
                    continue
                row = con.execute("SELECT id FROM categories WHERE name=?", (name,)).fetchone()
                if row:
                    new_id = int(row["id"])
                else:
                    cur = con.execute("INSERT INTO categories(name) VALUES (?)", (name,))
                    new_id = int(cur.lastrowid)
                try:
                    old_id = int(c.get("id"))
                    id_map[old_id] = new_id
                except Exception:
                    continue

            inserted = 0
            for p in purchases:
                old_cat_id = int(p.get("category_id"))
                new_cat_id = id_map.get(old_cat_id)
                if not new_cat_id:
                    continue
                con.execute(
                    """
                    INSERT INTO purchases(user_id, category_id, item_name, price, purchased_on, is_eco_friendly, eco_tags_json)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        int(user_id),
                        int(new_cat_id),
                        (p.get("item_name") or "").strip(),
                        float(p.get("price") or 0.0),
                        p.get("purchased_on"),
                        int(p.get("is_eco_friendly") or 0),
                        p.get("eco_tags_json") or "[]",
                    ),
                )
                inserted += 1
        return inserted
    except BackupRestoreError:
        raise
    except Exception as e:
        log_error("DAL.import_user_data_from_json", str(e))
        raise BackupRestoreError("Could not restore data.") from e

