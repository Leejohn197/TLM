from __future__ import annotations

BROWSER_MODES = {"normal", "guest", "incognito", "profile"}
BROWSER_SESSION_STATUSES = {"starting", "filling", "ready", "fallback", "failed", "released"}
ACTIVE_BROWSER_SESSION_STATUSES = {"active", "starting", "filling", "ready", "fallback"}
ACCOUNT_STATUSES = {"idle", "active", "locked"}
ENV_TAGS = {"TEST", "UAT", "PRE"}

STATUS_LABELS = {
    "idle": "空闲",
    "active": "使用中",
    "locked": "被占用",
}

BROWSER_MODE_LABELS = {
    "normal": "普通页签",
    "guest": "访客模式",
    "incognito": "无痕模式",
    "profile": "个人资料",
}
