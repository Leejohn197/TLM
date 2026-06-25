from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from .database import utc_now
from .models import ACTIVE_BROWSER_SESSION_STATUSES


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    if "extra_fields" in data and isinstance(data["extra_fields"], str):
        try:
            data["extra_fields"] = json.loads(data["extra_fields"])
        except json.JSONDecodeError:
            data["extra_fields"] = {}
    return data


def list_systems(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            s.*,
            COUNT(a.id) AS account_count,
            SUM(CASE WHEN a.status = 'idle' THEN 1 ELSE 0 END) AS idle_count,
            SUM(CASE WHEN a.status = 'active' THEN 1 ELSE 0 END) AS active_count,
            SUM(CASE WHEN a.status = 'locked' THEN 1 ELSE 0 END) AS locked_count
        FROM systems s
        LEFT JOIN accounts a ON a.system_id = s.id
        GROUP BY s.id
        ORDER BY s.sort_order ASC, s.name ASC
        """
    ).fetchall()
    return [row_to_dict(row) or {} for row in rows]


def get_system(conn: sqlite3.Connection, system_id: str) -> dict[str, Any] | None:
    return row_to_dict(conn.execute("SELECT * FROM systems WHERE id = ?", (system_id,)).fetchone())


def create_system(conn: sqlite3.Connection, data: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    system_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO systems (id, name, login_url, env_tag, note, sort_order, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            system_id,
            data["name"],
            data["login_url"],
            data["env_tag"],
            data.get("note", ""),
            int(data.get("sort_order", 100)),
            now,
            now,
        ),
    )
    log(conn, "create_system", system_id, None, None, "success", f"新增系统：{data['name']}")
    return get_system(conn, system_id) or {}


def update_system(conn: sqlite3.Connection, system_id: str, data: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    conn.execute(
        """
        UPDATE systems
        SET name = ?, login_url = ?, env_tag = ?, note = ?, sort_order = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            data["name"],
            data["login_url"],
            data["env_tag"],
            data.get("note", ""),
            int(data.get("sort_order", 100)),
            now,
            system_id,
        ),
    )
    log(conn, "update_system", system_id, None, None, "success", f"更新系统：{data['name']}")
    return get_system(conn, system_id) or {}


def delete_system(conn: sqlite3.Connection, system_id: str) -> None:
    conn.execute("DELETE FROM systems WHERE id = ?", (system_id,))
    log(conn, "delete_system", system_id, None, None, "success", "删除系统")


def list_accounts(conn: sqlite3.Connection, system_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM accounts
        WHERE system_id = ?
        ORDER BY
            CASE status WHEN 'idle' THEN 0 WHEN 'active' THEN 1 ELSE 2 END,
            role_label ASC,
            display_name ASC
        """,
        (system_id,),
    ).fetchall()
    return [row_to_dict(row) or {} for row in rows]


def get_account(conn: sqlite3.Connection, account_id: str) -> dict[str, Any] | None:
    return row_to_dict(conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone())


def create_account(conn: sqlite3.Connection, system_id: str, data: dict[str, Any], password_enc: str) -> dict[str, Any]:
    now = utc_now()
    account_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO accounts (
            id, system_id, role_label, display_name, username, password_enc,
            status, session_id, extra_fields, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 'idle', NULL, ?, ?, ?)
        """,
        (
            account_id,
            system_id,
            data["role_label"],
            data["display_name"],
            data["username"],
            password_enc,
            json.dumps(data.get("extra_fields", {}), ensure_ascii=False),
            now,
            now,
        ),
    )
    log(conn, "create_account", system_id, account_id, None, "success", f"新增账号：{data['display_name']}")
    return get_account(conn, account_id) or {}


def set_account_status(
    conn: sqlite3.Connection,
    account_id: str,
    status: str,
    session_id: str | None = None,
) -> None:
    conn.execute(
        "UPDATE accounts SET status = ?, session_id = ?, updated_at = ? WHERE id = ?",
        (status, session_id, utc_now(), account_id),
    )


def create_browser_session(
    conn: sqlite3.Connection,
    system_id: str,
    account_id: str,
    browser_mode: str,
    context_key: str,
) -> str:
    session_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO browser_sessions (
            id, system_id, account_id, browser_mode, context_key, status, message, created_at, released_at
        )
        VALUES (?, ?, ?, ?, ?, 'starting', ?, ?, NULL)
        """,
        (session_id, system_id, account_id, browser_mode, context_key, "正在启动浏览器", utc_now()),
    )
    return session_id


def get_browser_session(conn: sqlite3.Connection, session_id: str) -> dict[str, Any] | None:
    return row_to_dict(conn.execute("SELECT * FROM browser_sessions WHERE id = ?", (session_id,)).fetchone())


def update_browser_session_status(
    conn: sqlite3.Connection,
    session_id: str,
    status: str,
    message: str,
) -> None:
    released_at = utc_now() if status in {"failed", "released"} else None
    conn.execute(
        """
        UPDATE browser_sessions
        SET status = ?, message = ?, released_at = COALESCE(?, released_at)
        WHERE id = ?
        """,
        (status, message, released_at, session_id),
    )


def release_browser_session(conn: sqlite3.Connection, session_id: str, message: str = "账号已释放") -> None:
    conn.execute(
        "UPDATE browser_sessions SET status = 'released', message = ?, released_at = ? WHERE id = ?",
        (message, utc_now(), session_id),
    )


def active_session_for_context(
    conn: sqlite3.Connection,
    system_id: str,
    context_key: str,
) -> dict[str, Any] | None:
    placeholders = ", ".join("?" for _ in ACTIVE_BROWSER_SESSION_STATUSES)
    return row_to_dict(
        conn.execute(
            f"""
            SELECT * FROM browser_sessions
            WHERE system_id = ? AND context_key = ? AND status IN ({placeholders})
            LIMIT 1
            """,
            (system_id, context_key, *ACTIVE_BROWSER_SESSION_STATUSES),
        ).fetchone()
    )


def active_guest_session_count(conn: sqlite3.Connection) -> int:
    placeholders = ", ".join("?" for _ in ACTIVE_BROWSER_SESSION_STATUSES)
    row = conn.execute(
        f"SELECT COUNT(*) FROM browser_sessions WHERE browser_mode = 'guest' AND status IN ({placeholders})",
        tuple(ACTIVE_BROWSER_SESSION_STATUSES),
    ).fetchone()
    return int(row[0])


def active_accounts_for_system(conn: sqlite3.Connection, system_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM accounts WHERE system_id = ? AND status = 'active'",
        (system_id,),
    ).fetchone()
    return int(row[0])


def log(
    conn: sqlite3.Connection,
    action: str,
    system_id: str | None,
    account_id: str | None,
    browser_mode: str | None,
    result: str,
    message: str,
) -> None:
    conn.execute(
        """
        INSERT INTO operation_logs (id, action, system_id, account_id, browser_mode, result, message, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), action, system_id, account_id, browser_mode, result, message, utc_now()),
    )


def list_logs(conn: sqlite3.Connection, limit: int = 30) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT l.*, s.name AS system_name, a.display_name AS account_name
        FROM operation_logs l
        LEFT JOIN systems s ON s.id = l.system_id
        LEFT JOIN accounts a ON a.id = l.account_id
        ORDER BY l.created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [row_to_dict(row) or {} for row in rows]


def clear_logs(conn: sqlite3.Connection) -> int:
    cur = conn.execute("DELETE FROM operation_logs")
    return cur.rowcount


def update_account(
    conn: sqlite3.Connection,
    account_id: str,
    data: dict[str, Any],
    password_enc: str | None,
) -> dict[str, Any]:
    now = utc_now()
    if password_enc is not None:
        conn.execute(
            """
            UPDATE accounts
            SET role_label = ?, display_name = ?, username = ?, password_enc = ?, updated_at = ?
            WHERE id = ?
            """,
            (data["role_label"], data["display_name"], data["username"], password_enc, now, account_id),
        )
    else:
        conn.execute(
            """
            UPDATE accounts
            SET role_label = ?, display_name = ?, username = ?, updated_at = ?
            WHERE id = ?
            """,
            (data["role_label"], data["display_name"], data["username"], now, account_id),
        )
    return get_account(conn, account_id) or {}


def delete_account(conn: sqlite3.Connection, account_id: str) -> None:
    conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
