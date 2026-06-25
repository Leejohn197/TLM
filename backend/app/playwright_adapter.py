from __future__ import annotations

import logging
import platform
import re
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FillRequest:
    system_id: str
    account_id: str
    login_url: str
    username: str
    password: str
    browser_mode: str
    session_id: str
    profile_directory: str | None = None


@dataclass(frozen=True)
class FillResult:
    status: str
    message: str
    captcha_required: bool = True


# ------------------------------------------------------------------
# Chrome binary location helpers
# ------------------------------------------------------------------

def _chrome_executable() -> str:
    """Return the path to the user's installed Chrome binary."""
    system = platform.system()
    if system == "Darwin":
        path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if Path(path).exists():
            return path
    elif system == "Windows":
        for candidate in [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]:
            if Path(candidate).exists():
                return candidate
        found = shutil.which("chrome") or shutil.which("chrome.exe")
        if found:
            return found
    else:
        found = (
            shutil.which("google-chrome")
            or shutil.which("google-chrome-stable")
            or shutil.which("chromium")
        )
        if found:
            return found
    raise RuntimeError("未找到 Chrome 浏览器，请确保已安装 Google Chrome")


def _chrome_user_data_dir() -> Path:
    """Return the default Chrome user data directory."""
    system = platform.system()
    home = Path.home()
    if system == "Darwin":
        return home / "Library" / "Application Support" / "Google" / "Chrome"
    if system == "Windows":
        return home / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
    return home / ".config" / "google-chrome"


# ------------------------------------------------------------------
# Adapter
# ------------------------------------------------------------------

class FillAdapter:
    """Manages Playwright + real Chrome browser sessions for auto-filling login forms.

    Uses the user's installed Chrome executable, not Playwright's bundled
    Chromium binary.
    """

    def __init__(self) -> None:
        self._active_sessions: dict[str, dict[str, Any]] = {}

    def start_fill(self, request: FillRequest) -> FillResult:
        """Launch a background thread that opens Chrome and fills credentials.

        Returns immediately so the HTTP handler is non-blocking.
        """
        thread = threading.Thread(
            target=self._fill_worker,
            args=(request,),
            daemon=True,
            name=f"pw-fill-{request.session_id}",
        )
        thread.start()
        return FillResult(
            status="filling",
            message="正在打开 Chrome 并填充…",
            captcha_required=True,
        )

    # ------------------------------------------------------------------
    # Background worker
    # ------------------------------------------------------------------

    def _fill_worker(self, request: FillRequest) -> None:
        """Run inside a daemon thread – must never raise."""
        pw = None
        browser = None
        try:
            self._mark_session_status(request.session_id, "filling", "正在打开 Chrome 并定位登录页")
            pw = sync_playwright().start()
            browser, page = self._launch_and_navigate(pw, request)

            if browser is None or page is None:
                # Fallback occurred, Chrome opened via subprocess
                logger.warning("Session %s: 已通过原生方式打开浏览器，无法自动填充密码", request.session_id)
                self._mark_session_status(
                    request.session_id,
                    "fallback",
                    "已回退为原生 Chrome 打开页面，请手动登录",
                )
                try:
                    pw.stop()
                except Exception:
                    pass
                # We still store a dummy session so manual release works
                self._active_sessions[request.session_id] = {
                    "pw": None,
                    "browser": None,
                    "page": None,
                }
                return

            # Register cleanup when the user closes the page
            def _on_page_close(_: object) -> None:
                self._cleanup_session(request.session_id)

            page.on("close", _on_page_close)

            # ------ Wait for the SPA login form to render ------
            # Many login pages are SPAs (Vue, React) that render asynchronously.
            # We wait for either a password field or a significant input to appear.
            logger.info(
                "Session %s: waiting for login form to render…",
                request.session_id,
            )
            try:
                page.locator('input[type="password"]').first.wait_for(
                    state="visible", timeout=15_000,
                )
            except Exception:
                # If no password field found, wait a bit and try anyway
                logger.warning("Password field not visible after 15s, proceeding with fill attempt")
                time.sleep(2)

            # ------ Fill username ------
            username_filled = self._fill_username(page, request.username)

            # ------ Fill password ------
            password_filled = self._fill_password(page, request.password)

            # ------ Detect & focus captcha ------
            captcha_found = self._focus_captcha_if_present(page)

            # Store the live session so the browser stays open
            self._active_sessions[request.session_id] = {
                "pw": pw,
                "browser": browser,
                "page": page,
            }

            status_parts = []
            if username_filled:
                status_parts.append("用户名")
            if password_filled:
                status_parts.append("密码")
            if status_parts:
                msg = f"已填充：{'、'.join(status_parts)}"
                if captcha_found:
                    msg += "，验证码框已聚焦"
            else:
                msg = "未能定位到输入框，请手动填写"

            self._mark_session_status(request.session_id, "ready", msg)
            logger.info("Session %s: %s", request.session_id, msg)

        except Exception as exc:
            logger.exception("Session %s: fill worker failed", request.session_id)
            self._fail_session(request, f"填充失败：{exc}")
            # Cleanup on failure
            try:
                if browser is not None:
                    browser.close()
            except Exception:
                pass
            try:
                if pw is not None:
                    pw.stop()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Browser launch – ALWAYS uses real Chrome, not Playwright Chromium
    # ------------------------------------------------------------------

    def _launch_and_navigate(self, pw, request: FillRequest):
        """Launch the user's real Chrome and navigate to the login URL.

        Returns (browser, page).
        """
        chrome_executable = _chrome_executable()
        logger.info("Launching browser using Chrome executable: %s", chrome_executable)

        # Build extra Chrome args based on browser mode
        extra_args: list[str] = [
            "--no-first-run",
            "--no-default-browser-check",
            "--window-size=1920,1080",
        ]

        if request.browser_mode == "guest":
            extra_args.append("--guest")
        elif request.browser_mode == "incognito":
            extra_args.append("--incognito")
        elif request.browser_mode == "profile" and request.profile_directory:
            extra_args.append(f"--profile-directory={request.profile_directory}")

        # Use launch_persistent_context for profile mode (to load user's profile data)
        # Use regular launch for other modes (temp profile for isolation)
        if request.browser_mode == "profile" and request.profile_directory:
            user_data_dir = str(_chrome_user_data_dir())
            try:
                context = pw.chromium.launch_persistent_context(
                    user_data_dir,
                    executable_path=chrome_executable,
                    headless=False,
                    no_viewport=True,
                    args=extra_args,
                    ignore_default_args=["--enable-automation"],
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(request.login_url, wait_until="domcontentloaded", timeout=30_000)
                # For persistent context, browser is the context itself
                return context, page
            except Exception as e:
                logger.warning("launch_persistent_context failed: %s", e)
                logger.info("Falling back to subprocess launch for profile mode.")
                from .browser_launcher import open_login_page

                open_login_page(request.login_url, request.browser_mode, request.profile_directory)
                return None, None
        else:
            try:
                browser = pw.chromium.launch(
                    executable_path=chrome_executable,
                    headless=False,
                    args=extra_args,
                    ignore_default_args=["--enable-automation"],
                )
                context = browser.new_context(no_viewport=True)
                page = context.new_page()
                page.goto(request.login_url, wait_until="domcontentloaded", timeout=30_000)
                return browser, page
            except Exception as e:
                logger.warning("Chrome launch through Playwright failed: %s", e)
                logger.info("Falling back to native Chrome launch.")
                from .browser_launcher import open_login_page

                open_login_page(request.login_url, request.browser_mode, request.profile_directory)
                return None, None

    # ------------------------------------------------------------------
    # Field-filling strategies (SPA-aware with proper waits)
    # ------------------------------------------------------------------

    @staticmethod
    def _fill_username(page, username: str) -> bool:
        """Try several strategies to locate and fill the username field.

        Returns True if username was filled successfully.
        """
        # Strategy 1: Find by name/id attributes (most reliable)
        strategies = [
            (
                "name/id 属性匹配",
                'input[name*="user" i], input[name*="account" i], '
                'input[name*="login" i], input[name*="name" i], '
                'input[id*="user" i], input[id*="account" i], '
                'input[id*="login" i], input[id*="name" i]',
            ),
            (
                "placeholder 匹配",
                'input[placeholder*="用户" i], input[placeholder*="账号" i], '
                'input[placeholder*="手机" i], input[placeholder*="邮箱" i], '
                'input[placeholder*="username" i], input[placeholder*="account" i], '
                'input[placeholder*="email" i], input[placeholder*="login" i]',
            ),
            (
                "type=text 第一个可见",
                'input[type="text"]:visible',
            ),
        ]

        for label, selector in strategies:
            try:
                locator = page.locator(selector).first
                if locator.is_visible(timeout=2_000):
                    locator.click()
                    locator.fill(username)
                    logger.info("用户名已填充 (策略: %s)", label)
                    return True
            except Exception:
                logger.debug("用户名策略 '%s' 未匹配", label)

        # Strategy 4: Find the input that appears just before the password field
        try:
            password_el = page.locator('input[type="password"]').first
            if password_el.is_visible(timeout=1_000):
                # Get the parent form or container, find text inputs within it
                # Try to get preceding sibling input
                all_inputs = page.locator(
                    'input:not([type="password"]):not([type="hidden"])'
                    ':not([type="checkbox"]):not([type="radio"])'
                    ':not([type="submit"]):not([type="button"])'
                )
                count = all_inputs.count()
                for i in range(count):
                    inp = all_inputs.nth(i)
                    try:
                        if inp.is_visible(timeout=500):
                            inp.click()
                            inp.fill(username)
                            logger.info("用户名已填充 (策略: password 前方 input)")
                            return True
                    except Exception:
                        continue
        except Exception:
            logger.debug("密码前方 input 策略失败")

        logger.warning("未能定位到用户名输入框")
        return False

    @staticmethod
    def _fill_password(page, password: str) -> bool:
        """Fill the first visible password input. Returns True on success."""
        try:
            pwd_locator = page.locator('input[type="password"]').first
            pwd_locator.wait_for(state="visible", timeout=5_000)
            pwd_locator.click()
            pwd_locator.fill(password)
            logger.info("密码已填充")
            return True
        except Exception:
            logger.warning("未能定位到密码输入框")
            return False

    @staticmethod
    def _focus_captcha_if_present(page) -> bool:
        """If a captcha / verification-code input exists and is visible, focus it.

        Returns True if a captcha field was found and focused.
        """
        try:
            captcha_locator = page.locator(
                'input[name*="captcha" i], input[name*="code" i], '
                'input[name*="verify" i], input[name*="sms" i], '
                'input[placeholder*="验证码" i], input[placeholder*="captcha" i], '
                'input[placeholder*="验证" i]',
            )
            if captcha_locator.first.is_visible(timeout=2_000):
                captcha_locator.first.focus()
                logger.info("验证码输入框已聚焦")
                return True
        except Exception:
            logger.debug("未检测到验证码输入框")
        return False

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def close_session(self, session_id: str) -> None:
        """Close the browser and Playwright instance for session_id."""
        session = self._active_sessions.pop(session_id, None)
        if session is None:
            return
        try:
            session["browser"].close()
        except Exception:
            pass
        try:
            session["pw"].stop()
        except Exception:
            pass
        logger.info("Session %s closed", session_id)

    def _cleanup_session(self, session_id: str) -> None:
        """Internal callback invoked when the page is closed by the user."""
        session = self._active_sessions.pop(session_id, None)
        if session is None:
            return
        self._release_session(session_id, "浏览器页面已关闭，账号自动释放")
        try:
            session["pw"].stop()
        except Exception:
            pass
        logger.info("Session %s: 用户关闭页面，会话已清理", session_id)

    @staticmethod
    def _mark_session_status(session_id: str, status: str, message: str) -> None:
        try:
            from .database import connect
            from . import repositories as repo

            with connect() as conn:
                repo.update_browser_session_status(conn, session_id, status, message)
        except Exception:
            logger.exception("Session %s: failed to persist status '%s'", session_id, status)

    @staticmethod
    def _fail_session(request: FillRequest, message: str) -> None:
        try:
            from .database import connect
            from . import repositories as repo

            with connect() as conn:
                repo.update_browser_session_status(conn, request.session_id, "failed", message)
                repo.set_account_status(conn, request.account_id, "idle", None)
                repo.log(conn, "fill", request.system_id, request.account_id, request.browser_mode, "failed", message)
        except Exception:
            logger.exception("Session %s: failed to persist failure state", request.session_id)

    @staticmethod
    def _release_session(session_id: str, message: str) -> None:
        try:
            from .database import connect
            from . import repositories as repo

            with connect() as conn:
                session = repo.get_browser_session(conn, session_id)
                if not session or session["status"] in {"failed", "released"}:
                    return
                repo.release_browser_session(conn, session_id, message)
                repo.set_account_status(conn, session["account_id"], "idle", None)
                repo.log(
                    conn,
                    "release_account",
                    session["system_id"],
                    session["account_id"],
                    session["browser_mode"],
                    "success",
                    message,
                )
        except Exception:
            logger.exception("Session %s: failed to persist release state", session_id)


# ----------------------------------------------------------------------
# Module-level singleton
# ----------------------------------------------------------------------

_adapter_instance: FillAdapter | None = None


def get_adapter() -> FillAdapter:
    """Return (or create) the module-level FillAdapter singleton."""
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = FillAdapter()
    return _adapter_instance
