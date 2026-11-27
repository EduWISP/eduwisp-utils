# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Michele Salerno e i contributori di EduWISP
import os
import socket
import tempfile
import threading

import pytest
from django.db import OperationalError

from eduwisp_utils import health, queue

pytestmark = pytest.mark.django_db

REMOTE = {"REMOTE_ADDR": "203.0.113.7"}
VIA_NGINX = {"REMOTE_ADDR": "", "HTTP_X_FORWARDED_FOR": "203.0.113.7"}
LOCAL = {"REMOTE_ADDR": ""}


class FakeValkey:
    """Server Valkey finto su socket Unix: risponde ad AUTH e PING."""

    def __init__(self, password=None):
        self.password = password
        self.path = os.path.join(tempfile.mkdtemp(), "valkey.sock")
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(self.path)
        self.server.listen()
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            with conn:
                authed = self.password is None
                buffer = b""
                while True:
                    data = conn.recv(1024)
                    if not data:
                        break
                    buffer += data
                    if b"AUTH" in buffer and buffer.endswith(b"\r\n") and buffer.count(b"$") >= 2:
                        authed = self.password.encode() in buffer
                        conn.sendall(b"+OK\r\n" if authed else b"-WRONGPASS invalid\r\n")
                        buffer = b""
                    elif b"PING" in buffer:
                        conn.sendall(b"+PONG\r\n" if authed else b"-NOAUTH\r\n")
                        buffer = b""

    def url(self, password=None):
        auth = f":{password}@" if password else ""
        return f"redis+socket://{auth}{self.path}"

    def close(self):
        self.server.close()


@pytest.fixture
def valkey():
    server = FakeValkey(password="segreto-di-prova")
    yield server
    server.close()


def test_tutto_funziona(client, settings, valkey):
    settings.CELERY_BROKER_URL = valkey.url("segreto-di-prova")
    response = client.get("/health/", **REMOTE)
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"database": "ok", "migrations": "ok", "queue": "ok"},
    }
    assert "no-cache" in response["Cache-Control"]


def test_database_fermo_risponde_503(client, monkeypatch):
    def fermo():
        raise OperationalError("connection refused")

    monkeypatch.setattr(health, "check_database", fermo)
    response = client.get("/health/", **REMOTE)
    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "error"
    assert "details" not in response.json()


def test_coda_irraggiungibile(client, settings):
    settings.CELERY_BROKER_URL = "redis+socket:///percorso/inesistente.sock"
    response = client.get("/health/", **REMOTE)
    assert response.status_code == 503
    assert response.json()["checks"]["queue"] == "error"


def test_password_della_coda_sbagliata(client, settings, valkey):
    settings.CELERY_BROKER_URL = valkey.url("sbagliata")
    response = client.get("/health/", **LOCAL)
    assert response.status_code == 503
    assert "autenticazione rifiutata" in response.json()["details"]["queue"]["error"]


def test_senza_coda_configurata_il_controllo_non_c_e(client):
    assert set(client.get("/health/", **REMOTE).json()["checks"]) == {"database", "migrations"}


def test_migrazioni_in_sospeso(client, monkeypatch):
    class Executor:
        def __init__(self, connection):
            self.loader = type("L", (), {"graph": type("G", (), {"leaf_nodes": lambda s: []})()})()

        def migration_plan(self, targets):
            return [("app", "0002")]

    monkeypatch.setattr(health, "MigrationExecutor", Executor)
    response = client.get("/health/", **REMOTE)
    assert response.status_code == 503
    assert response.json()["checks"]["migrations"] == "error"


def test_dettagli_solo_in_locale(client, settings):
    settings.CELERY_BROKER_URL = "redis+socket:///percorso/inesistente.sock"
    locale = client.get("/health/", **LOCAL).json()
    assert "error" in locale["details"]["queue"]
    assert "ms" in locale["details"]["database"]
    # Da nginx (X-Forwarded-For presente) niente dettagli, anche se arriva dal socket Unix.
    assert "details" not in client.get("/health/", **VIA_NGINX).json()
    assert "details" not in client.get("/health/", **REMOTE).json()


def test_solo_get(client):
    assert client.post("/health/", **REMOTE).status_code == 405


def test_url_coda_non_supportato():
    with pytest.raises(queue.QueueError):
        queue.ping("rediss://localhost:6380")
