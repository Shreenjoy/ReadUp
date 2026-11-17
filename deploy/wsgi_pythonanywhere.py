"""
WSGI entry point for PythonAnywhere.

Paste the contents of this file into the WSGI configuration file that PythonAnywhere creates
for the web app (Web tab -> "WSGI configuration file"), replacing everything in it.

PythonAnywhere does not read the project's .env automatically for the web app process, so the
environment is loaded here before Django starts. The file itself stays out of git.
"""

import os
import sys

import environ

PROJECT_ROOT = "/home/joys3/readup"          # change if the clone lives elsewhere

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load secrets before Django reads settings.
environ.Env.read_env(os.path.join(PROJECT_ROOT, ".env"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "readup.settings")

from django.core.wsgi import get_wsgi_application   # noqa: E402

application = get_wsgi_application()
