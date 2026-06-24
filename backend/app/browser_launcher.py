from __future__ import annotations

import json
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .models import BROWSER_MODES


class BrowserLaunchError(Exception):
    pass


@dataclass(frozen=True)
class BrowserLaunchResult:
    browser_mode: str
    login_url: str
    command_label: str


def open_login_page(
    login_url: str,
    browser_mode: str,
    profile_directory: str | None = None,
) -> BrowserLaunchResult:
    if browser_mode not in BROWSER_MODES:
        raise BrowserLaunchError("浏览器模式不合法")
    if browser_mode == "profile" and not profile_directory:
        raise BrowserLaunchError("请选择 Chrome 个人资料")
    if profile_directory:
        profile_directory = _validated_profile_directory(profile_directory)
    command = _build_command(login_url, browser_mode, profile_directory)
    try:
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        raise BrowserLaunchError(f"无法启动 Chrome：{exc}") from exc
    return BrowserLaunchResult(
        browser_mode=browser_mode,
        login_url=login_url,
        command_label=_command_label(browser_mode),
    )


def list_chrome_profiles() -> list[dict[str, str]]:
    profile_root = _profile_root()
    local_state = profile_root / "Local State"
    profiles: list[dict[str, str]] = []
    if local_state.exists():
        try:
            payload = json.loads(local_state.read_text(encoding="utf-8"))
            info_cache = payload.get("profile", {}).get("info_cache", {})
            for directory, info in info_cache.items():
                name = str(info.get("name") or directory).strip() or directory
                profiles.append(
                    {
                        "id": directory,
                        "name": name,
                        "directory": directory,
                    }
                )
        except (OSError, json.JSONDecodeError):
            profiles = []
    if not profiles:
        profiles = [{"id": "Default", "name": "Default", "directory": "Default"}]
    return sorted(profiles, key=lambda item: (item["name"].lower(), item["directory"].lower()))


def _build_command(
    login_url: str,
    browser_mode: str,
    profile_directory: str | None = None,
) -> list[str]:
    system_name = platform.system()
    if system_name == "Darwin":
        return _macos_command(login_url, browser_mode, profile_directory)
    if system_name == "Windows":
        return _windows_command(login_url, browser_mode, profile_directory)
    return _linux_command(login_url, browser_mode, profile_directory)


def _macos_command(
    login_url: str,
    browser_mode: str,
    profile_directory: str | None = None,
) -> list[str]:
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if browser_mode == "normal":
        return ["open", "-a", "Google Chrome", login_url]
    if browser_mode == "guest":
        return [chrome, "--guest", "--new-window", login_url]
    if browser_mode == "profile":
        return [chrome, f"--profile-directory={profile_directory}", "--new-window", login_url]
    return [chrome, "--incognito", "--new-window", login_url]


def _windows_command(
    login_url: str,
    browser_mode: str,
    profile_directory: str | None = None,
) -> list[str]:
    chrome = _find_windows_chrome()
    if browser_mode == "normal":
        return [chrome, "--new-window", login_url]
    if browser_mode == "guest":
        return [chrome, "--guest", "--new-window", login_url]
    if browser_mode == "profile":
        return [chrome, f"--profile-directory={profile_directory}", "--new-window", login_url]
    return [chrome, "--incognito", "--new-window", login_url]


def _linux_command(
    login_url: str,
    browser_mode: str,
    profile_directory: str | None = None,
) -> list[str]:
    chrome = shutil.which("google-chrome") or shutil.which("google-chrome-stable") or shutil.which("chromium")
    if not chrome:
        raise BrowserLaunchError("未找到 Chrome/Chromium 可执行文件")
    if browser_mode == "normal":
        return [chrome, "--new-window", login_url]
    if browser_mode == "guest":
        return [chrome, "--guest", "--new-window", login_url]
    if browser_mode == "profile":
        return [chrome, f"--profile-directory={profile_directory}", "--new-window", login_url]
    return [chrome, "--incognito", "--new-window", login_url]


def _profile_root() -> Path:
    system_name = platform.system()
    home = Path.home()
    if system_name == "Darwin":
        return home / "Library" / "Application Support" / "Google" / "Chrome"
    if system_name == "Windows":
        return home / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
    return home / ".config" / "google-chrome"


def _validated_profile_directory(profile_directory: str) -> str:
    allowed = {profile["directory"] for profile in list_chrome_profiles()}
    if profile_directory not in allowed:
        raise BrowserLaunchError("Chrome 个人资料不存在或不可用")
    return profile_directory


def _find_windows_chrome() -> str:
    chrome = shutil.which("chrome") or shutil.which("chrome.exe")
    if chrome:
        return chrome
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for candidate in candidates:
        if shutil.os.path.exists(candidate):
            return candidate
    raise BrowserLaunchError("未找到 Chrome 可执行文件")


def _command_label(browser_mode: str) -> str:
    return {
        "normal": "普通页签",
        "guest": "访客模式",
        "incognito": "无痕模式",
        "profile": "个人资料",
    }.get(browser_mode, browser_mode)
