# Product

## Register

product

## Users

TLM is used by test engineers who rotate across daily verification work and need to enter 3-8 business systems quickly without mixing environments or reusing occupied accounts. Test leads maintain the system and account catalog, monitor account status, and resolve locked or conflicting sessions.

## Product Purpose

TLM is the first-phase Test Login Manager for a future automation testing platform. Its immediate job is to reduce repeated login work, make account occupancy visible, and provide a safe handoff point for browser filling while leaving CAPTCHA submission to a human. Success means a tester can choose a system, pick an idle role account, confirm a browser mode, and reach the target login page with account fields filled in a predictable workflow.

## Brand Personality

Calm, operational, exact. The interface should feel like a reliable internal control desk: compact enough for daily use, explicit about risk states, and quiet enough to stay out of the tester's way.

## Anti-references

Do not make this feel like a marketing dashboard, a decorative landing page, a mobile-first app, or a generic admin template full of oversized cards. Avoid copying the referenced prototype literally; use it only for workflow shape and information hierarchy.

## Design Principles

Keep the primary action unambiguous: system, account, browser mode, and fill status must always be visible before the user commits.

Represent state before style: idle, active, locked, validation failure, and local service availability need consistent visual treatment.

Prefer dense but readable structure: the target user scans many systems and role accounts repeatedly, so spacing should support comparison rather than spectacle.

Design for local-first evolution: the UI should work against local SQLite and REST today while preserving names and boundaries that can migrate to a platform backend later.

Respect security expectations: passwords are never displayed in lists, are masked in confirmation, and should not appear in logs or UI state.

## Accessibility & Inclusion

Target WCAG 2.1 AA contrast for text and controls. Use system fonts for Chinese and English readability on macOS and Windows. Motion should be minimal, state-driven, and disabled under reduced-motion preferences. The first version is desktop Web only and intentionally does not optimize for mobile layouts.
