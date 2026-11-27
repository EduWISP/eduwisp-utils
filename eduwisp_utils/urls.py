# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Michele Salerno e i contributori di EduWISP
"""Da includere nel progetto: path("", include("eduwisp_utils.urls"))."""

from django.urls import path

from .health import health

urlpatterns = [path("health/", health, name="eduwisp-health")]
