from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .security import PasswordCipher

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.environ.get("TLM_DB_PATH", ROOT_DIR / "backend" / "data" / "tlm.sqlite3"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS systems (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                login_url TEXT NOT NULL,
                env_tag TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(name, env_tag)
            );

            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                system_id TEXT NOT NULL REFERENCES systems(id) ON DELETE CASCADE,
                role_label TEXT NOT NULL,
                display_name TEXT NOT NULL,
                username TEXT NOT NULL,
                password_enc TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'idle',
                session_id TEXT,
                extra_fields TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(system_id, username)
            );

            CREATE TABLE IF NOT EXISTS browser_sessions (
                id TEXT PRIMARY KEY,
                system_id TEXT NOT NULL REFERENCES systems(id) ON DELETE CASCADE,
                account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                browser_mode TEXT NOT NULL,
                context_key TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                released_at TEXT
            );

            CREATE TABLE IF NOT EXISTS operation_logs (
                id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                system_id TEXT,
                account_id TEXT,
                browser_mode TEXT,
                result TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM systems").fetchone()[0]
        if count == 0:
            seed(conn)


def seed(conn: sqlite3.Connection) -> None:
    cipher = PasswordCipher()
    now = utc_now()
    systems = [
        {
            "id": str(uuid.uuid4()),
            "name": "招标采购平台",
            "login_url": "https://tender.example.test/login",
            "env_tag": "TEST",
            "note": "高频冒烟验证系统",
            "sort_order": 10,
            "accounts": [
                ("管理员", "赵管理员", "admin_tender"),
                ("采购专员", "李采购", "buyer_li"),
                ("供应商 A", "供应商测试 A", "vendor_a"),
            ],
        },
        {
            "id": str(uuid.uuid4()),
            "name": "OA 审批系统",
            "login_url": "https://oa.uat.example.test/login",
            "env_tag": "UAT",
            "note": "审批链路验证",
            "sort_order": 20,
            "accounts": [
                ("审批人", "王审批", "approver_wang"),
                ("申请人", "陈申请", "requester_chen"),
            ],
        },
        {
            "id": str(uuid.uuid4()),
            "name": "ERP 沙箱",
            "login_url": "https://erp.example.test/sign-in",
            "env_tag": "TEST",
            "note": "财务与库存流程",
            "sort_order": 30,
            "accounts": [
                ("财务", "孙财务", "finance_sun"),
                ("仓库", "周仓库", "stock_zhou"),
            ],
        },
    ]
    for system in systems:
        conn.execute(
            """
            INSERT INTO systems (id, name, login_url, env_tag, note, sort_order, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                system["id"],
                system["name"],
                system["login_url"],
                system["env_tag"],
                system["note"],
                system["sort_order"],
                now,
                now,
            ),
        )
        for role_label, display_name, username in system["accounts"]:
            conn.execute(
                """
                INSERT INTO accounts (
                    id, system_id, role_label, display_name, username, password_enc,
                    status, session_id, extra_fields, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'idle', NULL, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    system["id"],
                    role_label,
                    display_name,
                    username,
                    cipher.encrypt("demo-password"),
                    json.dumps({}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
