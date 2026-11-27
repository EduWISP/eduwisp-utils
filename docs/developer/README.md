# Utility condivise — documentazione per sviluppatori

## Endpoint di stato `/health/`

```python
# settings.py
INSTALLED_APPS = [..., "eduwisp_utils"]

# urls.py
urlpatterns += [path("", include("eduwisp_utils.urls"))]
```

Controlli, tutti obbligatori:

| Nome | Cosa verifica |
|---|---|
| `database` | connessione e `SELECT 1` sul database predefinito |
| `migrations` | nessuna migrazione da applicare |
| `queue` | `AUTH` e `PING` su Valkey/Redis, solo se è impostato `CELERY_BROKER_URL` (o `EDUWISP_HEALTH_QUEUE_URL`) |

Risposta: **200** se tutti i controlli riescono, altrimenti **503**, sempre con `Cache-Control: no-store`.

```json
{"status": "ok", "checks": {"database": "ok", "migrations": "ok", "queue": "ok"}}
```

**Privacy e sicurezza:** la risposta pubblica contiene solo lo stato, nessun dato personale. Errori e tempi di ogni controllo (`details`) compaiono solo per le richieste **locali** che non passano dal proxy: indirizzo `127.0.0.1`, `::1` o socket Unix, **senza** l'intestazione `X-Forwarded-For` che nginx aggiunge sempre. Solo `GET` e `HEAD`.

Il controllo della coda non usa librerie esterne: parla direttamente il protocollo di Valkey. Supporta `redis://`, `unix://` e `redis+socket://` (il formato di Celery); non supporta TLS, perché in EduWISP la coda è solo locale.

Impostazioni facoltative: `EDUWISP_HEALTH_QUEUE_URL`, `EDUWISP_HEALTH_TIMEOUT` (secondi, predefinito 2).

## Test

```sh
pip install -e ".[test]" ruff
pytest -q && ruff check . && ruff format --check .
```

---

🇬🇧 *`/health/` checks the database, pending migrations and the Valkey queue; returns 200 or 503 with a minimal JSON body and no personal data. Error details and timings only for local requests not coming through the proxy. No external dependencies for the queue check.*
