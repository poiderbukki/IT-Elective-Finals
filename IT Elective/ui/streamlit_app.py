from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import altair as alt
import streamlit as st

from bll.services import AuthService, BackupRestoreService, BllError, CatalogService, PurchaseService
from dal.db import DbConfig, connect, init_db, seed_from_json
from dal.repositories import CategoryRepository, PurchaseRepository, UserRepository
from dto.models import NewPurchaseDTO, UpdatePurchaseDTO

from bll.auth import hash_password
from bll.scoring import BIG_O_COMPLEXITY_NOTE


APP_DB = Path(__file__).resolve().parent.parent / "sustainable_shopping.sqlite3"
SEED_JSON = Path(__file__).resolve().parent.parent / "seed.json"
BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"


def _get_services():
    if "con" not in st.session_state:
        cfg = DbConfig(db_path=APP_DB)
        con = connect(cfg)
        init_db(con)
        seed_from_json(con, SEED_JSON, password_hasher=hash_password)
        st.session_state["con"] = con

    con = st.session_state["con"]
    users = UserRepository(con)
    cats = CategoryRepository(con)
    purchases = PurchaseRepository(con)
    return (
        AuthService(users),
        CatalogService(cats),
        PurchaseService(purchases, cats),
        BackupRestoreService(con),
    )

def _inject_styles():
    # Simple Streamlit theming via CSS (light/dark toggle).
    # Accent color: Shopee-ish red/orange.
    dark = bool(st.session_state.get("dark_mode", False))
    bg = "#0B1220" if dark else "#ffffff"
    surface = "#0F172A" if dark else "#ffffff"
    surface2 = "#0B1326" if dark else "#f7f7f7"
    border = "rgba(255,255,255,0.10)" if dark else "rgba(0,0,0,0.08)"
    text = "#E5E7EB" if dark else "#111827"
    muted = "#9CA3AF" if dark else "#4B5563"

    css = """
        <style>
        :root{
            --text: __TEXT__;
            --muted: __MUTED__;
        }

        /* Remove Streamlit header + disable collapsible sidebar control */
        [data-testid="stHeader"] { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }

        /* Force sidebar to always be visible (avoid "stuck collapsed") */
        section[data-testid="stSidebar"]{
            display: block !important;
            visibility: visible !important;
            transform: none !important;
            margin-left: 0 !important;
            width: 20rem !important;
            min-width: 20rem !important;
            max-width: 20rem !important;
        }
        /* Ensure main content doesn't overlap sidebar */
        @media (min-width: 992px){
            .block-container{
                padding-left: 2rem !important;
            }
        }

        /* Base */
        html, body, [data-testid="stAppViewContainer"] {
            background: __BG__;
            color: var(--text) !important;
        }
        /* Force readable text across Streamlit containers */
        h1, h2, h3, h4, h5, h6, p, li, label, span, div {
            color: var(--text);
        }
        [data-testid="stCaptionContainer"], .stCaption, small {
            color: var(--muted) !important;
        }
        /* Widget labels */
        [data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] span {
            color: var(--text) !important;
            font-weight: 600;
        }

        /* Sidebar */
        [data-testid="stSidebar"] {
            background: __SURFACE2__;
            border-right: 1px solid __BORDER__;
        }
        [data-testid="stSidebar"] * { color: var(--text) !important; }

        /* Tabs */
        div[role="tablist"] button {
            border-radius: 10px !important;
            padding: 8px 14px !important;
        }
        div[role="tab"][aria-selected="true"] {
            color: #ffffff !important;
            background: #EE4D2D !important;
        }

        /* Buttons */
        .stButton > button {
            border-radius: 10px !important;
            font-weight: 600 !important;
            background: __SURFACE__ !important;
            color: var(--text) !important;
            border: 1px solid __BORDER__ !important;
        }
        .stButton > button:hover {
            border-color: __BORDER__ !important;
            background: __SURFACE__ !important;
        }
        /* Primary button */
        .stButton > button[kind="primary"],
        .stButton > button[data-testid="baseButton-primary"] {
            background: #EE4D2D !important;
            color: #ffffff !important;
            border: 1px solid #EE4D2D !important;
        }
        .stButton > button[kind="primary"]:hover,
        .stButton > button[data-testid="baseButton-primary"]:hover {
            filter: brightness(0.96);
        }

        /* Inputs */
        input, select, textarea, [data-baseweb="input"] input {
            border-radius: 12px !important;
            border: 1px solid __BORDER__ !important;
            color: var(--text) !important;
            background: __SURFACE__ !important;
        }
        /* Streamlit BaseWeb widgets (selectbox, number input, date input) */
        [data-baseweb="select"] > div,
        [data-baseweb="select"] div[role="combobox"],
        [data-baseweb="select"] input {
            background: __SURFACE__ !important;
            color: var(--text) !important;
        }
        [data-baseweb="select"] > div {
            border-radius: 12px !important;
            border: 1px solid __BORDER__ !important;
        }
        [data-baseweb="select"] svg {
            fill: var(--text) !important;
        }

        /* Number input +/- buttons area */
        [data-baseweb="input"] {
            background: __SURFACE__ !important;
            border-radius: 12px !important;
        }
        [data-baseweb="input"] > div {
            border-radius: 12px !important;
        }
        [data-baseweb="input"] button {
            background: __SURFACE__ !important;
            color: var(--text) !important;
            border-left: 1px solid __BORDER__ !important;
        }
        [data-baseweb="input"] button:hover {
            background: rgba(238, 77, 45, 0.06) !important;
        }

        /* Date input calendar icon */
        [data-testid="stDateInput"] svg {
            fill: var(--text) !important;
        }

        /* Checkboxes/radios/toggles */
        [data-testid="stCheckbox"] label p,
        [data-testid="stRadio"] label p,
        [data-testid="stToggle"] label p {
            color: var(--text) !important;
        }
        input[type="checkbox"], input[type="radio"] {
            accent-color: #EE4D2D;
        }

        /* Alerts / warnings */
        [data-testid="stAlert"] * { color: var(--text) !important; }

        /* Metrics */
        [data-testid="metric-container"] {
            border: 1px solid __BORDER__;
            border-radius: 16px;
            padding: 12px 14px;
            background: __SURFACE__;
            box-shadow: 0 6px 20px rgba(0,0,0,0.03);
        }

        /* Cards / containers */
        .block-container {
            padding-top: 10px;
            padding-bottom: 10px;
        }

        /* Links */
        a { color: #EE4D2D; text-decoration: none; }
        a:hover { text-decoration: underline; }
        </style>
        """
    css = (
        css.replace("__TEXT__", text)
        .replace("__MUTED__", muted)
        .replace("__BG__", bg)
        .replace("__SURFACE__", surface)
        .replace("__SURFACE2__", surface2)
        .replace("__BORDER__", border)
    )
    st.markdown(css, unsafe_allow_html=True)


def _ensure_session_keys():
    st.session_state.setdefault("current_user", None)
    logged_in = st.session_state.get("current_user") is not None
    st.session_state.setdefault("nav_page", "Dashboard" if logged_in else "Login")
    st.session_state.setdefault("_prev_logged_in", logged_in)
    st.session_state.setdefault("dark_mode", False)


def _logout():
    st.session_state["current_user"] = None


def main():
    st.set_page_config(
        page_title="Checkable Purchase Logger (Prototype)",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _ensure_session_keys()
    _inject_styles()

    auth_svc, cat_svc, purchase_svc, backup_svc = _get_services()

    # Keep navigation state consistent across login/logout transitions.
    logged_in = st.session_state.get("current_user") is not None
    prev_logged_in = st.session_state.get("_prev_logged_in", logged_in)
    if logged_in and not prev_logged_in:
        st.session_state["nav_page"] = "Dashboard"
    elif not logged_in and prev_logged_in:
        st.session_state["nav_page"] = "Login"
    st.session_state["_prev_logged_in"] = logged_in

    _sidebar_nav()

    page = st.session_state["nav_page"]
    if page == "Login":
        _page_login(auth_svc)
        return
    if page == "Dashboard":
        _page_dashboard(purchase_svc)
        return
    if page == "Purchases":
        _page_purchases(cat_svc, purchase_svc, backup_svc)
        return
    if page == "About":
        _page_about()
        return


def _sidebar_nav():
    with st.sidebar:
        st.title("Menu")
        user = st.session_state.get("current_user")
        st.toggle("Dark mode", key="dark_mode")
        if user:
            st.caption(f"Logged in as **{user['display_name']}** (`{user['username']}`)")
            st.button("Logout", on_click=_logout, use_container_width=True)
            st.divider()
            st.radio(
                "Navigate",
                options=["Dashboard", "Purchases", "About"],
                key="nav_page",
                label_visibility="collapsed",
            )
        else:
            st.radio("Navigate", options=["Login", "About"], key="nav_page", label_visibility="collapsed")


def _page_login(auth_svc: AuthService):
    st.header("Login")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Existing user")
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login", type="primary", use_container_width=True):
            try:
                user = auth_svc.login(username, password)
                st.session_state["current_user"] = asdict(user)
                st.rerun()
            except BllError as e:
                st.error(str(e))

        st.caption("Seed user: `admin` / `admin123` (change this in `seed.json`).")

    with col2:
        st.subheader("Register (prototype)")
        r_username = st.text_input("New username", key="reg_username")
        r_display = st.text_input("Display name", key="reg_display")
        r_password = st.text_input("New password", type="password", key="reg_password")
        if st.button("Create account", use_container_width=True):
            try:
                user = auth_svc.register(r_username, r_password, r_display)
                st.success("Account created. You can login now.")
                st.session_state["login_username"] = user.username
            except BllError as e:
                st.error(str(e))


def _page_dashboard(purchase_svc: PurchaseService):
    st.header("Dashboard")
    user = st.session_state["current_user"]
    user_id = int(user["id"])

    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("SDG 12 Sustainability Score")
        if st.button("Recompute score (async)", type="primary", use_container_width=True):
            st.session_state["score_refresh"] = datetime.utcnow().isoformat()

        with st.spinner("Computing score..."):
            score = asyncio.run(purchase_svc.compute_score_async(user_id))

        st.metric("Sustainability score", f"{score.sustainability_score:.2f}/100")
        st.metric("Eco-friendly %", f"{score.eco_percentage:.2f}%")
        st.metric("Carbon footprint (proxy)", f"{score.carbon_footprint_score:.2f}/100")
        st.metric("Waste reduction (proxy)", f"{score.waste_reduction_score:.2f}/100")
        st.metric("Risk rating", f"{score.risk_rating:.2f}/100")
        if score.notes:
            st.info(score.notes)

    with c2:
        st.subheader("Monthly trend")
        summaries = purchase_svc.monthly_summaries(user_id)
        if not summaries:
            st.warning("No data yet. Add purchases to see trends.")
            return

        data = [
            {
                "month": f"{s.year}-{s.month:02d}",
                "eco_percentage": s.eco_percentage,
                "sustainability_score": s.sustainability_score,
                "total_purchases": s.total_purchases,
            }
            for s in summaries
        ]

        base = alt.Chart(alt.Data(values=data)).encode(x=alt.X("month:N", title="Month"))
        chart1 = base.mark_line(point=True).encode(
            y=alt.Y("eco_percentage:Q", title="Eco-friendly %"),
            tooltip=["month:N", "eco_percentage:Q", "total_purchases:Q"],
        )
        chart2 = base.mark_line(point=True, color="#2E8B57").encode(
            y=alt.Y("sustainability_score:Q", title="Sustainability score"),
            tooltip=["month:N", "sustainability_score:Q", "total_purchases:Q"],
        )

        st.altair_chart(
            alt.layer(chart1, chart2).resolve_scale(y="independent").properties(height=350),
            use_container_width=True,
        )


def _page_purchases(cat_svc: CatalogService, purchase_svc: PurchaseService, backup_svc: BackupRestoreService):
    st.header("Purchases (CRUD)")
    user = st.session_state["current_user"]
    user_id = int(user["id"])

    # Flash notifications (reliable across reruns)
    flash = st.session_state.pop("_flash_message", None)
    if flash:
        st.toast(flash)
        st.success(flash)

    try:
        categories = cat_svc.list_categories()
        purchases = purchase_svc.list_purchases(user_id)
    except BllError as e:
        st.error(str(e))
        return

    cat_options = {c.name: c.id for c in categories}
    cat_names = list(cat_options.keys()) or ["(no categories)"]

    tabs = st.tabs(["Add", "Edit", "Delete", "View", "Backup/Restore"])

    with tabs[0]:
        st.subheader("Add purchase")
        item = st.text_input("Item name", key="add_item")
        cat_name = st.selectbox("Category", options=cat_names, key="add_cat")
        price = st.number_input("Price", min_value=0.0, value=0.0, step=0.5, key="add_price")
        purchased_on = st.date_input("Date", value=date.today(), key="add_date")
        is_eco = st.checkbox("Eco-friendly", value=False, key="add_eco")
        st.caption("Sustainability criteria (majority rule: 3+ met = Eco-Friendly)")
        c1 = st.checkbox("Recyclable or biodegradable packaging", key="add_c1")
        c2 = st.checkbox("Minimal plastic usage", key="add_c2")
        c3 = st.checkbox("Reusable design", key="add_c3")
        c4 = st.checkbox("Locally sourced materials", key="add_c4")
        c5 = st.checkbox("Certified sustainable production", key="add_c5")
        tags = st.text_input("Eco tags (comma-separated)", key="add_tags")

        if st.button("Save", type="primary", use_container_width=True, key="add_save"):
            try:
                dto = NewPurchaseDTO(
                    item_name=item,
                    category_id=int(cat_options[cat_name]),
                    price=float(price),
                    purchased_on=purchased_on,
                    is_eco_friendly=bool(is_eco),
                    eco_tags=_parse_tags(tags),
                    criteria_met=_selected_criteria(c1, c2, c3, c4, c5),
                )
                purchase_svc.add_purchase(user_id, dto)
                st.session_state["_flash_message"] = "Item added."
                st.rerun()
            except (BllError, KeyError) as e:
                st.error(str(e))

    with tabs[1]:
        st.subheader("Edit purchase")
        if not purchases:
            st.info("No purchases yet.")
        else:
            purchases_by_id = {int(p.id): p for p in purchases}

            def _label(pid: int) -> str:
                p0 = purchases_by_id[int(pid)]
                return f"{p0.purchased_on} • {p0.item_name} • {p0.category_name} • ₱{p0.price:.2f}"

            label_to_id = {_label(pid): int(pid) for pid in purchases_by_id.keys()}

            def _split_tags(tags: Sequence[str]):
                criteria = []
                free_tags = []
                for t in tags or []:
                    if isinstance(t, str) and t.lower().startswith("criteria:"):
                        criteria.append(t.split(":", 1)[1].strip())
                    else:
                        free_tags.append(t)
                return free_tags, criteria

            def _apply_selected_to_form(pid: int) -> None:
                p0 = purchases_by_id[int(pid)]
                free_tags, criteria = _split_tags(p0.eco_tags)
                st.session_state["edit_item"] = p0.item_name
                st.session_state["edit_cat"] = p0.category_name if p0.category_name in cat_names else cat_names[0]
                st.session_state["edit_price"] = float(p0.price)
                st.session_state["edit_date"] = p0.purchased_on
                st.session_state["edit_eco"] = bool(p0.is_eco_friendly)
                st.session_state["edit_tags"] = ", ".join([str(x) for x in free_tags if str(x).strip()])
                st.session_state["edit_c1"] = "recyclable_or_biodegradable_packaging" in criteria
                st.session_state["edit_c2"] = "minimal_plastic_usage" in criteria
                st.session_state["edit_c3"] = "reusable_design" in criteria
                st.session_state["edit_c4"] = "locally_sourced_materials" in criteria
                st.session_state["edit_c5"] = "certified_sustainable_production" in criteria

            # Selection widget: change selection => repopulate the form fields.
            default_id = int(purchases[0].id)
            st.session_state.setdefault("edit_purchase_id", default_id)
            # If Streamlit has an old stored string value, convert it.
            cur_val = st.session_state.get("edit_purchase_id")
            if isinstance(cur_val, str):
                st.session_state["edit_purchase_id"] = int(label_to_id.get(cur_val, default_id))
            elif isinstance(cur_val, int):
                if cur_val not in purchases_by_id:
                    st.session_state["edit_purchase_id"] = default_id

            def _on_edit_selection_change():
                raw = st.session_state.get("edit_purchase_id")
                if isinstance(raw, str):
                    pid = int(label_to_id.get(raw, default_id))
                    st.session_state["edit_purchase_id"] = pid
                else:
                    pid = int(raw)
                _apply_selected_to_form(pid)

            selected_id = st.selectbox(
                "Select purchase",
                options=list(purchases_by_id.keys()),
                format_func=_label,
                key="edit_purchase_id",
                on_change=_on_edit_selection_change,
            )

            # First render (or if user cleared session) populate fields.
            if st.session_state.get("_edit_form_bound_to") != int(selected_id):
                _apply_selected_to_form(int(selected_id))
                st.session_state["_edit_form_bound_to"] = int(selected_id)

            st.text_input("Item name", key="edit_item")
            st.selectbox("Category", options=cat_names, key="edit_cat")
            st.number_input("Price", min_value=0.0, step=0.5, key="edit_price")
            st.date_input("Date", key="edit_date")
            st.checkbox("Eco-friendly", key="edit_eco")
            st.caption("Sustainability criteria (majority rule: 3+ met = Eco-Friendly)")
            st.checkbox("Recyclable or biodegradable packaging", key="edit_c1")
            st.checkbox("Minimal plastic usage", key="edit_c2")
            st.checkbox("Reusable design", key="edit_c3")
            st.checkbox("Locally sourced materials", key="edit_c4")
            st.checkbox("Certified sustainable production", key="edit_c5")
            st.text_input("Eco tags (comma-separated)", key="edit_tags")

            if st.button("Update", type="primary", use_container_width=True, key="edit_save"):
                try:
                    dto = UpdatePurchaseDTO(
                        id=int(selected_id),
                        item_name=st.session_state.get("edit_item", ""),
                        category_id=int(cat_options[st.session_state.get("edit_cat", cat_names[0])]),
                        price=float(st.session_state.get("edit_price", 0.0)),
                        purchased_on=st.session_state.get("edit_date", date.today()),
                        is_eco_friendly=bool(st.session_state.get("edit_eco", False)),
                        eco_tags=_parse_tags(st.session_state.get("edit_tags", "")),
                        criteria_met=_selected_criteria(
                            bool(st.session_state.get("edit_c1", False)),
                            bool(st.session_state.get("edit_c2", False)),
                            bool(st.session_state.get("edit_c3", False)),
                            bool(st.session_state.get("edit_c4", False)),
                            bool(st.session_state.get("edit_c5", False)),
                        ),
                    )
                    purchase_svc.update_purchase(user_id, dto)
                    st.success("Updated.")
                    st.rerun()
                except (BllError, KeyError) as e:
                    st.error(str(e))

    with tabs[2]:
        st.subheader("Delete purchase")
        if not purchases:
            st.info("No purchases yet.")
        else:
            purchases_by_id = {int(p.id): p for p in purchases}

            def _del_label(pid: int) -> str:
                p0 = purchases_by_id[int(pid)]
                return f"{p0.purchased_on} • {p0.item_name} • ₱{p0.price:.2f}"

            del_label_to_id = {_del_label(pid): int(pid) for pid in purchases_by_id.keys()}
            default_del_id = int(purchases[0].id)
            st.session_state.setdefault("del_purchase_id", default_del_id)
            cur_del = st.session_state.get("del_purchase_id")
            if isinstance(cur_del, str):
                st.session_state["del_purchase_id"] = int(del_label_to_id.get(cur_del, default_del_id))
            elif isinstance(cur_del, int) and cur_del not in purchases_by_id:
                st.session_state["del_purchase_id"] = default_del_id

            selected_del_id = st.selectbox(
                "Select purchase to delete",
                options=list(purchases_by_id.keys()),
                format_func=_del_label,
                key="del_purchase_id",
            )
            p = purchases_by_id[int(selected_del_id)]
            st.warning("This cannot be undone.")
            if st.button("Delete", type="secondary", use_container_width=True, key="del_btn"):
                try:
                    purchase_svc.delete_purchase(user_id, int(p.id))
                    st.success("Deleted.")
                    st.rerun()
                except BllError as e:
                    st.error(str(e))

    with tabs[3]:
        st.subheader("View purchases")
        if not purchases:
            st.info("No purchases yet.")
        else:
            st.dataframe(
                [
                    {
                        "Date": str(p.purchased_on),
                        "Item": p.item_name,
                        "Category": p.category_name,
                        "Price": float(p.price),
                        "Eco-friendly": bool(p.is_eco_friendly),
                        "Tags": ", ".join(p.eco_tags),
                    }
                    for p in purchases
                ],
                use_container_width=True,
                hide_index=True,
            )

    with tabs[4]:
        st.subheader("Data Backup & Restore (FR5)")
        backup_name = st.text_input("Backup file name", value=f"backup_user_{user_id}.json", key="backup_name")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Export Backup JSON", use_container_width=True):
                try:
                    path = BACKUP_DIR / backup_name
                    exported = backup_svc.export_backup(user_id, path)
                    st.success(f"Exported to: {exported}")
                except BllError as e:
                    st.error(str(e))
        with col_b:
            restore_path = st.text_input(
                "Restore file path",
                value=str(BACKUP_DIR / backup_name),
                key="restore_path",
            )
            if st.button("Import / Restore JSON", use_container_width=True):
                try:
                    inserted = backup_svc.restore_backup(user_id, Path(restore_path))
                    st.success(f"Restore complete. Imported {inserted} purchases.")
                    st.rerun()
                except BllError as e:
                    st.error(str(e))


def _page_about():
    st.header("About")
    st.markdown(
        """
This app is like a smart shopping diary that helps you make better choices for the environment. 

Every time you buy something, you can quickly log it (what you bought, how much it cost, and when).

You can also mark if the item is eco-friendly (for example: reusable, recyclable, or low waste).

The app keeps track of your habits and gives you a score showing how many of your purchases are environmentally friendly.

It shows a simple monthly chart so you can see if you’re improving over time.

You can save your data and reload it anytime, so nothing gets lost.
"""
    )
    st.subheader("Big O Complexity (scoring)")
    st.markdown(
        """
- **Time**: **O(n)** — the app looks through your purchases once.
- **Space**: **O(1)** extra space — it only uses a few counters while computing.
"""
    )


def _parse_tags(s: str) -> Sequence[str]:
    parts = [p.strip() for p in (s or "").split(",")]
    tags = [p for p in parts if p]
    # small UI-level validation; BLL also validates
    return tags[:12]


def _selected_criteria(c1: bool, c2: bool, c3: bool, c4: bool, c5: bool) -> Sequence[str]:
    mapping = [
        ("recyclable_or_biodegradable_packaging", c1),
        ("minimal_plastic_usage", c2),
        ("reusable_design", c3),
        ("locally_sourced_materials", c4),
        ("certified_sustainable_production", c5),
    ]
    return [name for name, checked in mapping if checked]

