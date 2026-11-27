# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Michele Salerno e i contributori di EduWISP
"""Controllo minimo di Valkey/Redis (AUTH e PING), senza dipendenze esterne.

URL accettati: ``redis://``, ``unix://`` e ``redis+socket://`` (il formato di Celery/kombu
per i socket Unix). TLS (``rediss://``) non è supportato: in EduWISP la coda è solo locale
(ADR-0016).
"""

import socket
from urllib.parse import unquote, urlsplit


class QueueError(Exception):
    pass


def _command(*parts: str) -> bytes:
    encoded = [p.encode() for p in parts]
    out = [f"*{len(encoded)}\r\n".encode()]
    for p in encoded:
        out.append(f"${len(p)}\r\n".encode() + p + b"\r\n")
    return b"".join(out)


def _reply(sock: socket.socket) -> bytes:
    data = b""
    while not data.endswith(b"\r\n"):
        chunk = sock.recv(256)
        if not chunk:
            raise QueueError("connessione chiusa")
        data += chunk
    return data.rstrip(b"\r\n")


def connect(url: str, timeout: float) -> socket.socket:
    parts = urlsplit(url)
    if parts.scheme in ("unix", "redis+socket"):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(parts.path)
    elif parts.scheme == "redis":
        sock = socket.create_connection(
            (parts.hostname or "localhost", parts.port or 6379), timeout
        )
    else:
        raise QueueError(f"schema non supportato: {parts.scheme}")
    return sock


def ping(url: str, timeout: float = 2.0) -> None:
    """Solleva QueueError (o OSError) se la coda non risponde."""
    parts = urlsplit(url)
    with connect(url, timeout) as sock:
        if parts.password:
            auth = (
                ("AUTH", unquote(parts.username), unquote(parts.password))
                if parts.username
                else (
                    "AUTH",
                    unquote(parts.password),
                )
            )
            sock.sendall(_command(*auth))
            if _reply(sock) != b"+OK":
                raise QueueError("autenticazione rifiutata")
        sock.sendall(_command("PING"))
        if _reply(sock) != b"+PONG":
            raise QueueError("risposta inattesa a PING")
