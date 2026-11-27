# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Michele Salerno e i contributori di EduWISP
"""Endpoint di stato /health/ (ADR-0016), per Monit e per la procedura di aggiornamento.

Risposta pubblica minima: stato complessivo e stato di ogni controllo, nessun dato personale.
Dettagli (errori e tempi) solo per le richieste locali che non passano dal proxy.
"""

import time
from collections.abc import Callable

from django.conf import settings
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from . import queue

LOCAL_ADDRESSES = {"127.0.0.1", "::1", ""}  # "" = socket Unix di gunicorn


def check_database() -> None:
    with connections[DEFAULT_DB_ALIAS].cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()


def check_migrations() -> None:
    connection = connections[DEFAULT_DB_ALIAS]
    executor = MigrationExecutor(connection)
    pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
    if pending:
        raise RuntimeError(f"{len(pending)} migrazioni da applicare")


def queue_url() -> str | None:
    return getattr(settings, "EDUWISP_HEALTH_QUEUE_URL", None) or getattr(
        settings, "CELERY_BROKER_URL", None
    )


def check_queue() -> None:
    queue.ping(queue_url(), timeout=getattr(settings, "EDUWISP_HEALTH_TIMEOUT", 2.0))


def checks() -> dict[str, Callable[[], None]]:
    result = {"database": check_database, "migrations": check_migrations}
    if queue_url():
        result["queue"] = check_queue
    return result


def is_local(request) -> bool:
    # Le richieste da nginx hanno sempre X-Forwarded-For: non sono locali anche se arrivano
    # dal socket Unix. Sono locali solo quelle fatte direttamente sul server.
    return (
        request.META.get("REMOTE_ADDR", "") in LOCAL_ADDRESSES
        and "HTTP_X_FORWARDED_FOR" not in request.META
    )


@never_cache
@require_GET
def health(request):
    local = is_local(request)
    status, details = {}, {}
    for name, check in checks().items():
        start = time.monotonic()
        try:
            check()
            status[name] = "ok"
        except Exception as exc:  # noqa: BLE001 - qualunque errore rende il servizio non sano
            status[name] = "error"
            if local:
                details[name] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
        if local:
            details.setdefault(name, {})["ms"] = round((time.monotonic() - start) * 1000, 1)
    healthy = all(v == "ok" for v in status.values())
    body = {"status": "ok" if healthy else "error", "checks": status}
    if local:
        body["details"] = details
    return JsonResponse(body, status=200 if healthy else 503)
