from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FillRequest:
    system_id: str
    account_id: str
    login_url: str
    username: str
    password: str
    browser_mode: str
    session_id: str


@dataclass(frozen=True)
class FillResult:
    status: str
    message: str
    captcha_required: bool = True


class FillAdapter:
    """Boundary for the future Playwright integration.

    The user explicitly requested no Playwright script design in this phase.
    This adapter therefore only preserves the service contract.
    """

    def start_fill(self, request: FillRequest) -> FillResult:
        _ = request
        return FillResult(
            status="stubbed",
            message="已建立填充任务占位；本阶段未接入 Playwright 脚本。",
            captcha_required=True,
        )
