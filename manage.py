#!/usr/bin/env python
"""Utilidad de línea de comandos de Django para la Fototeca CCP."""

import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "No se pudo importar Django. En local, activa el entorno virtual "
            "(`source .venv/bin/activate`) y ejecuta "
            "`pip install -r requirements.txt`. En la consola de Railway el "
            "entorno está en /opt/venv: usa `/opt/venv/bin/python manage.py …`."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
