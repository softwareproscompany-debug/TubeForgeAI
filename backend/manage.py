#!/usr/bin/env python
"""Django management entry point for TubeForge AI.

This module exposes Django's manage.py entry point used to run management
commands (runserver, migrate, etc.) for the TubeForge AI backend.
"""

import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Is it installed and available on your PYTHONPATH?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
