#!/usr/bin/env python
"""VIP Network management entrypoint, in the spirit of Django's manage.py.

    uv run python manage.py createsuperuser          # asks e-mail and password (e-mail = login)
    uv run python manage.py changepassword admin@vipnetwork.com.br
    uv run python manage.py migrate
    uv run python manage.py makemigrations -m "add companies"
    uv run python manage.py runserver                # 3199, reload
    uv run python manage.py check

Non-interactive (CI, Docker):

    VIP_SUPERUSER_PASSWORD=... uv run python manage.py createsuperuser \
        --noinput --email admin@vipnetwork.com.br
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _use_project_venv() -> None:
    """`python manage.py ...` with any interpreter: re-run with backend/.venv when it exists.

    Like Django, the command should just work; the dependencies live in the project venv
    (`uv sync --extra dev`), not in the system Python.
    """
    here = Path(__file__).resolve().parent
    venv = here / ".venv"
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists() or Path(sys.prefix).resolve() == venv.resolve():
        return
    raise SystemExit(subprocess.call([str(python), str(here / "manage.py"), *sys.argv[1:]]))


if __name__ == "__main__":
    _use_project_venv()
    for stream in (sys.stdout, sys.stderr):  # accents on Windows consoles
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    os.chdir(Path(__file__).resolve().parent)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from app.management.commands import main

    sys.exit(main())
