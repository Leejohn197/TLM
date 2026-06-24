# Design System

## Overview

TLM now uses a glass-control-desk visual direction: translucent operational panels, cool light planes, soft elevation, and jelly-like feedback on selected controls. The interface should feel more tactile without becoming decorative enough to hide account state.

## Color

Use OKLCH tokens only in CSS. The product remains restrained, with a white/cool glass base, crimson primary actions, blue-cyan selection accents, and clear semantic state colors.

```css
:root {
  --bg: oklch(0.985 0.006 238);
  --glass: oklch(1 0 0 / 0.64);
  --glass-strong: oklch(1 0 0 / 0.78);
  --ink: oklch(0.205 0.019 250);
  --muted: oklch(0.425 0.027 250);
  --line: oklch(0.82 0.018 250 / 0.58);
  --primary: oklch(0.54 0.172 25);
  --accent: oklch(0.47 0.118 205);
  --success: oklch(0.55 0.13 150);
  --warning: oklch(0.66 0.15 72);
  --danger: oklch(0.56 0.18 28);
}
```

## Typography

Use `Inter`, `SF Pro Text`, `Segoe UI`, `PingFang SC`, `Microsoft YaHei`, and `system-ui` fallbacks. Product headings use fixed sizes, not viewport-scaled typography. Body copy stays at 14px-15px, dense labels at 12px-13px, and page titles at 22px-24px.

## Layout

The first version is desktop-only. The app shell keeps a fixed 236px system sidebar, a flexible content workspace, and a 48px fixed glass status bar. Account cards remain in a stable CSS grid so status badges and actions do not resize the layout.

## Components

Use glass treatment on shell surfaces, summary cells, command row, account cards, dialogs, toasts, and form controls. Keep card radius at 8px for a product-like feel. Buttons use soft elevation and active compression. Status badges use semantic fill and text, never color alone.

## Motion

Interaction should feel jelly-like but purposeful: selected account cards, active browser-mode segments, dialogs, toasts, and buttons get short elastic settling motion. Keep normal transitions under 250ms and respect `prefers-reduced-motion: reduce`.

## Content

Use concise Chinese labels. Avoid explanatory marketing copy inside the product. UI text should state current state and next action: "空闲", "使用中", "释放", "确认填充", "当前访客会话".
