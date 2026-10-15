# Changelog

All notable changes to TubeForge AI are documented here. Versions follow [Semantic Versioning](https://semver.org/).

## [1.0.0] — 2026-10-14

Initial production release. Live at https://tubeforge.aixentium.com.

### Stack
- Next.js 16.4.1 + React 19.3.1 (upgraded from 14)
- Django 5.2 + Django REST Framework
- PostgreSQL + Redis + Temporal (durable workflows)
- FFmpeg media engine, ComfyUI-compatible provider adapters
- Tailwind CSS v4

### Features
- 15-section command center (overview, research, projects, editor, publishing, analytics, etc.)
- 22-state Temporal workflow engine (research → generate → assemble → publish)
- Local-first AI provider gateway with server-side budgets
- YouTube OAuth + idempotent publishing
- Encrypted secrets vault (Fernet)

### Security
- Cross-owner isolation on all resources
- Admin-only system settings
- Scoped idempotency keys
