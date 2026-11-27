# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Michele Salerno e i contributori di EduWISP
"""Impostazioni del progetto di prova. Solo per test: mai in produzione."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SECRET_KEY = "solo-per-test-non-usare-in-produzione"
DEBUG = False
ALLOWED_HOSTS = ["testserver"]
INSTALLED_APPS = ["eduwisp_utils", "django.contrib.contenttypes", "django.contrib.auth"]
MIDDLEWARE = ["django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "eduwisp_utils.urls"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
