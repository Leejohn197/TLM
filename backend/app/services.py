from __future__ import annotations

import re
import sqlite3
from typing import Any

from . import repositories as repo
from .browser_launcher import BrowserLaunchError, list_chrome_profiles, open_login_page
from .models import ACCOUNT_STATUSES, BROWSER_MODES, ENV_TAGS
from .playwright_adapter import FillAdapter, FillRequest
from .security import PasswordCipher

URL_RE = re.compile(r"^https?://", re.IGNORECASE)


class ServiceError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def systems_payload(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return repo.list_systems(conn)


def accounts_payload(conn: sqlite3.Connection, system_id: str) -> list[dict[str, Any]]:
    require_system(conn, system_id)
    accounts = repo.list_accounts(conn, system_id)
    for account in accounts:
        account.pop("password_enc", None)
        account["password_mask"] = PasswordCipher.mask("")
    return accounts


def create_system(conn: sqlite3.Connection, data: dict[str, Any]) -> dict[str, Any]:
    clean = validate_system(data)
    try:
        return repo.create_system(conn, clean)
    except sqlite3.IntegrityError as exc:
        raise ServiceError("同名称 + 同环境的系统已存在") from exc


def update_system(conn: sqlite3.Connection, system_id: str, data: dict[str, Any]) -> dict[str, Any]:
    require_system(conn, system_id)
    clean = validate_system(data)
    try:
        return repo.update_system(conn, system_id, clean)
    except sqlite3.IntegrityError as exc:
        raise ServiceError("同名称 + 同环境的系统已存在") from exc


def delete_system(conn: sqlite3.Connection, system_id: str) -> None:
    require_system(conn, system_id)
    if repo.active_accounts_for_system(conn, system_id) > 0:
        raise ServiceError("该系统存在使用中的账号，禁止删除")
    repo.delete_system(conn, system_id)


def create_account(conn: sqlite3.Connection, system_id: str, data: dict[str, Any]) -> dict[str, Any]:
    require_system(conn, system_id)
    clean = validate_account(data)
    cipher = PasswordCipher()
    try:
        account = repo.create_account(conn, system_id, clean, cipher.encrypt(clean["password"]))
    except sqlite3.IntegrityError as exc:
        raise ServiceError("同一系统下用户名不允许重复") from exc
    account.pop("password_enc", None)
    account["password_mask"] = PasswordCipher.mask("")
    return account


def fill(conn: sqlite3.Connection, data: dict[str, Any]) -> dict[str, Any]:
    system_id = str(data.get("system_id", ""))
    account_id = str(data.get("account_id", ""))
    browser_mode = str(data.get("browser_mode", "normal"))
    context_key = str(data.get("context_key", "default-profile")).strip() or "default-profile"

    if browser_mode not in BROWSER_MODES:
        raise ServiceError("浏览器模式不合法")

    system = require_system(conn, system_id)
    account = require_account(conn, account_id)
    if account["system_id"] != system_id:
        raise ServiceError("账号不属于当前系统")
    if account["status"] == "active":
        raise ServiceError("该账号正在使用中，请先释放后再操作", 409)
    if account["status"] == "locked":
        raise ServiceError("该账号已被负责人标记为占用", 409)

    if browser_mode == "normal":
        existing = repo.active_session_for_context(conn, system_id, context_key)
        if existing:
            raise ServiceError("当前窗口已登录该系统，请新开访客/无痕模式", 409)

    session_id = repo.create_browser_session(conn, system_id, account_id, browser_mode, context_key)
    repo.set_account_status(conn, account_id, "active", session_id)

    cipher = PasswordCipher()
    adapter = FillAdapter()
    result = adapter.start_fill(
        FillRequest(
            system_id=system_id,
            account_id=account_id,
            login_url=system["login_url"],
            username=account["username"],
            password=cipher.decrypt(account["password_enc"]),
            browser_mode=browser_mode,
            session_id=session_id,
        )
    )
    repo.log(conn, "fill", system_id, account_id, browser_mode, result.status, result.message)
    return {
        "session_id": session_id,
        "result": result.status,
        "message": result.message,
        "captcha_required": result.captcha_required,
    }


def open_login(conn: sqlite3.Connection, data: dict[str, Any]) -> dict[str, Any]:
    system_id = str(data.get("system_id", ""))
    browser_mode = str(data.get("browser_mode", "normal"))
    profile_directory = data.get("chrome_profile_directory")
    if profile_directory is not None:
        profile_directory = str(profile_directory)
    if browser_mode not in BROWSER_MODES:
        raise ServiceError("浏览器模式不合法")

    system = require_system(conn, system_id)
    try:
        result = open_login_page(system["login_url"], browser_mode, profile_directory)
    except BrowserLaunchError as exc:
        repo.log(conn, "open_login", system_id, None, browser_mode, "failed", str(exc))
        raise ServiceError(str(exc), 500) from exc

    message = f"已用{result.command_label}打开：{system['name']}"
    repo.log(conn, "open_login", system_id, None, browser_mode, "success", message)
    return {
        "system_id": system_id,
        "system_name": system["name"],
        "login_url": result.login_url,
        "browser_mode": result.browser_mode,
        "message": message,
    }


def browser_profiles_payload() -> dict[str, Any]:
    return {"profiles": list_chrome_profiles()}


def account_status(conn: sqlite3.Connection, account_id: str) -> dict[str, Any]:
    account = require_account(conn, account_id)
    return {
        "id": account["id"],
        "status": account["status"],
        "session_id": account["session_id"],
        "updated_at": account["updated_at"],
    }


def release_account(conn: sqlite3.Connection, account_id: str) -> dict[str, Any]:
    account = require_account(conn, account_id)
    if account["status"] != "active":
        raise ServiceError("只有使用中的账号可以释放")
    if account.get("session_id"):
        repo.release_browser_session(conn, account["session_id"])
    repo.set_account_status(conn, account_id, "idle", None)
    repo.log(conn, "release_account", account["system_id"], account_id, None, "success", "账号已释放")
    return account_status(conn, account_id)


def lock_account(conn: sqlite3.Connection, account_id: str, locked: bool) -> dict[str, Any]:
    account = require_account(conn, account_id)
    if account["status"] == "active" and locked:
        raise ServiceError("使用中的账号不能手动标记为被占用")
    status = "locked" if locked else "idle"
    repo.set_account_status(conn, account_id, status, None)
    repo.log(conn, "lock_account", account["system_id"], account_id, None, "success", "账号状态已更新")
    return account_status(conn, account_id)


def update_account(conn: sqlite3.Connection, account_id: str, data: dict[str, Any]) -> dict[str, Any]:
    account = require_account(conn, account_id)
    role_label = str(data.get("role_label", "")).strip()
    display_name = str(data.get("display_name", "")).strip()
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if not role_label:
        raise ServiceError("角色名称为必填项")
    if not display_name:
        raise ServiceError("显示名称为必填项")
    if not username:
        raise ServiceError("用户名为必填项")
    clean = {"role_label": role_label, "display_name": display_name, "username": username}
    cipher = PasswordCipher()
    password_enc = cipher.encrypt(password) if password else None
    try:
        updated = repo.update_account(conn, account_id, clean, password_enc)
    except sqlite3.IntegrityError as exc:
        raise ServiceError("同一系统下用户名不允许重复") from exc
    updated.pop("password_enc", None)
    updated["password_mask"] = PasswordCipher.mask("")
    repo.log(conn, "update_account", account["system_id"], account_id, None, "success", f"更新账号：{display_name}")
    return updated


def delete_account(conn: sqlite3.Connection, account_id: str) -> None:
    account = repo.get_account(conn, account_id)
    if not account:
        raise ServiceError("账号不存在", 404)
    if account["status"] == "active":
        raise ServiceError("账号正在使用中，请先释放后再删除", 409)
    repo.delete_account(conn, account_id)
    repo.log(conn, "delete_account", account["system_id"], account_id, None, "success", f"删除账号：{account['display_name']}")


def browser_payload(conn: sqlite3.Connection) -> dict[str, Any]:
    return {"guest_sessions": repo.active_guest_session_count(conn)}


def logs_payload(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return repo.list_logs(conn)


def clear_logs(conn: sqlite3.Connection) -> int:
    deleted = repo.clear_logs(conn)
    repo.log(conn, "clear_logs", None, None, None, "success", f"已清除 {deleted} 条操作日志")
    return deleted


def validate_system(data: dict[str, Any]) -> dict[str, Any]:
    name = str(data.get("name", "")).strip()
    login_url = str(data.get("login_url", "")).strip()
    env_tag = str(data.get("env_tag", "TEST")).strip().upper()
    note = str(data.get("note", "")).strip()
    sort_order = data.get("sort_order", 100)
    if not name:
        raise ServiceError("系统名称为必填项")
    if not URL_RE.match(login_url):
        raise ServiceError("登录页 URL 必须以 http:// 或 https:// 开头")
    if env_tag not in ENV_TAGS:
        raise ServiceError("环境标签仅支持 TEST / UAT / PRE")
    return {
        "name": name,
        "login_url": login_url,
        "env_tag": env_tag,
        "note": note,
        "sort_order": int(sort_order),
    }


def validate_account(data: dict[str, Any]) -> dict[str, Any]:
    role_label = str(data.get("role_label", "")).strip()
    display_name = str(data.get("display_name", "")).strip()
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if not role_label:
        raise ServiceError("角色名称为必填项")
    if not display_name:
        raise ServiceError("显示名称为必填项")
    if not username:
        raise ServiceError("用户名为必填项")
    if not password:
        raise ServiceError("密码为必填项")
    return {
        "role_label": role_label,
        "display_name": display_name,
        "username": username,
        "password": password,
        "extra_fields": data.get("extra_fields", {}),
    }


def require_system(conn: sqlite3.Connection, system_id: str) -> dict[str, Any]:
    system = repo.get_system(conn, system_id)
    if not system:
        raise ServiceError("系统不存在", 404)
    return system


def require_account(conn: sqlite3.Connection, account_id: str) -> dict[str, Any]:
    account = repo.get_account(conn, account_id)
    if not account:
        raise ServiceError("账号不存在", 404)
    if account["status"] not in ACCOUNT_STATUSES:
        raise ServiceError("账号状态异常", 500)
    return account
