# Sistema de Resiliencia para MiBotTrading

**Fecha:** 2026-06-13
**Estado:** Aprobado
**Versión:** 1.0

## Resumen

Sistema completo de robustez para el bot de trading multi-exchange, diseñado para operación 24/7 sin supervisión. Cubre reintentos inteligentes, circuit breaker, monitoreo de salud, recuperación de estado y backup automático.

## Arquitectura

```
utils/resilience/
├── __init__.py              # Exporta decoradores y servicios
├── decorators.py            # @retry, @circuit_breaker, @timeout, @log_errors
├── retry_service.py         # Backoff exponencial con jitter
├── circuit_breaker.py       # Estados: closed/open/half-open por exchange
├── health_monitor.py        # Health checks periódicos + historial
├── state_recovery.py        # Snapshots + restauración de posición
├── error_handler.py         # Taxonomía de errores + logging estructurado
└── backup_manager.py        # Backup automático rotativo
```

### Flujo de datos

```
Exchange call → @timeout → @retry → @circuit_breaker → @log_errors → CCXT
                                 │
                           HealthMonitor ← cada 60s verifica conexiones
                                 │
                           StateRecovery ← antes de cada mutación crítica
                                 │
                           BackupManager ← backup automático cada 15 min
```

## Componentes

### 1. RetryService (`retry_service.py`)

Reintentos con backoff exponencial y jitter.

```
@retry(
    max_retries=3,
    base_delay=1.0,
    max_delay=30.0,
    backoff_factor=2.0,
    jitter=True,
    retry_on=[NetworkError, RateLimitError, ExchangeNotAvailable],
    on_retry=notify_retry
)
```

**Algoritmo de espera:**
```
delay = min(base_delay * (backoff_factor ** attempt), max_delay)
if jitter:
    delay = delay * random.uniform(0.5, 1.5)
```

**Excepciones no reintentables:** `AuthenticationError`, `BadSymbol`, `BadRequest`, `InvalidOrder`

### 2. CircuitBreaker (`circuit_breaker.py`)

Tres estados por exchange:

| Estado | Comportamiento |
|--------|---------------|
| **CLOSED** | Normal. Pasan todas las requests. |
| **OPEN** | 5 fallos consecutivos. Bloquea requests 60s. Lanza `CircuitBreakerOpenError`. |
| **HALF_OPEN** | Después de 60s, deja pasar 1 request de prueba. Éxito → CLOSED. Fallo → OPEN. |

```python
@circuit_breaker(
    name="bitget",
    failure_threshold=5,
    reset_timeout=60,
    half_open_max_requests=1,
)
```

**Persistencia:** El estado del circuit breaker se guarda en `{DATA_DIR}/circuit_breaker_state.json` para sobrevivir a reinicios.

### 3. Timeout (`decorators.py`)

Timeouts configurables por tipo de operación:

| Operación | Timeout |
|-----------|---------|
| fetch_ticker | 15s |
| fetch_balance | 30s |
| create_order | 60s |
| cancel_order | 30s |
| set_leverage | 30s |
| fetch_position | 30s |

Implementado como wrapper de `asyncio.wait_for` con logging adicional.

### 4. Error Handler (`error_handler.py`)

Taxonomía de errores:

- `ExchangeConnectionError` — Error de conexión con exchange
- `RateLimitExceeded` — Rate limit alcanzado
- `OrderRejected` — Orden rechazada por el exchange
- `InsufficientBalance` — Saldo insuficiente
- `PositionNotFound` — Posición no encontrada
- `CircuitBreakerOpenError` — Circuit breaker bloqueando requests
- `MaxRetriesExceeded` — Se agotaron los reintentos

**Logging estructurado:**
```json
{
    "event": "exchange_error",
    "exchange": "bitget",
    "method": "fetch_balance",
    "error": "...",
    "error_type": "ExchangeConnectionError",
    "duration_ms": 1234,
    "circuit_state": "closed",
    "retry_attempt": 2
}
```

### 5. HealthMonitor (`health_monitor.py`)

Monitoreo periódico de salud de conexiones.

- Intervalo: 60s (configurable)
- Health check: `fetch_ticker` con símbolo conocido (BTC/USDT)
- Almacena historial en `health_history.json`

```python
@dataclass
class ExchangeHealth:
    exchange_id: str
    status: str  # "healthy" | "degraded" | "down"
    last_ok: Optional[float]     # timestamp
    consecutive_failures: int
    avg_latency_ms: float
    circuit_breaker_state: str   # "closed" | "open" | "half_open"
```

**Integración con watchdog:** Se ejecuta como tarea asíncrona dentro del watchdog existente en `engine.py`.

### 6. StateRecovery (`state_recovery.py`)

Snapshots de estado antes de operaciones críticas.

```python
@dataclass
class Checkpoint:
    id: str
    timestamp: float
    operation: str  # "create_position" | "modify_sl" | "modify_tp"
    data: dict      # snapshot del estado
    status: str     # "pending" | "completed" | "failed"
```

**Al iniciar:** Si hay checkpoints "pending" → intenta restaurar el estado y completar la operación.

**Rotación:** Máximo 50 checkpoints. Los más antiguos se eliminan automáticamente.

**Ubicación:** `{DATA_DIR}/recovery/checkpoints.json`

### 7. BackupManager (`backup_manager.py`)

Backup automático rotativo de archivos críticos.

| Archivo | Intervalo | Retención |
|---------|-----------|-----------|
| posiciones.json | 15 min | 24 backups |
| config.json | 15 min | 24 backups |
| canales.json | 15 min | 24 backups |

**Nomenclatura:** `positions_20260613_143000.json.gz`
**Compresión:** gzip
**Restauración automática:** Al iniciar, si `posiciones.json` está corrupto, restaura el último backup válido.

## Integración con Código Existente

### Decoradores a aplicar

| Módulo | Método | Decoradores |
|--------|--------|-------------|
| `exchange_service.py` | `get_balance()` | `@retry`, `@timeout`, `@circuit_breaker`, `@log_errors` |
| `exchange_service.py` | `get_ticker_price()` | `@retry`, `@timeout`, `@circuit_breaker` |
| `exchange_service.py` | `create_client()` | `@retry`, `@timeout` |
| `exchange_service.py` | `set_leverage()` | `@retry`, `@circuit_breaker` |
| `exchange_service.py` | `fetch_position()` | `@retry`, `@timeout` |
| `exchange_service.py` | `cancel_order()` | `@retry`, `@timeout` |
| `core/engine.py` | `execute_signal()` | `@log_errors` |
| `core/engine.py` | `watchdog()` | Integrar `HealthMonitor` |
| `core/manager.py` | `save()` | `@retry` + `StateRecovery` |
| `services/market_data.py` | `fetch_top20()` | `@retry`, `@timeout` |

### Archivos a modificar

- **Nuevos (7):** `utils/resilience/__init__.py`, `decorators.py`, `retry_service.py`, `circuit_breaker.py`, `health_monitor.py`, `state_recovery.py`, `backup_manager.py`
- **Modificados (3):** `services/exchange_service.py`, `core/engine.py`, `core/manager.py`

## Orden de Implementación

1. **retry_service.py** — Backoff exponencial + jitter (base del sistema)
2. **circuit_breaker.py** — Estados y lógica de circuit breaker
3. **decorators.py** — Decoradores @retry, @circuit_breaker, @timeout, @log_errors
4. **health_monitor.py** — Monitor de salud + integración con watchdog
5. **state_recovery.py + backup_manager.py** — Persistencia robusta
6. **Aplicar decoradores** — Integrar en exchange_service.py, engine.py, manager.py

## Tests

| Archivo | Cobertura |
|---------|-----------|
| `tests/test_retry_service.py` | Backoff, jitter, max_retries, excepciones, callback |
| `tests/test_circuit_breaker.py` | Estados, transiciones, umbral, persistencia |
| `tests/test_decorators.py` | @retry, @circuit_breaker como decoradores en funciones async/sync |
| `tests/test_health_monitor.py` | Health checks, detección fallos, recuperación, historial |
| `tests/test_state_recovery.py` | Snapshots, restauración, límite, persistencia |
| `tests/test_backup_manager.py` | Backup, rotación, compresión, restauración |

## Consideraciones

- **No romper API existente:** Los decoradores son aditivos, no modifican firmas de funciones.
- **No agregar dependencias:** Todo el sistema usa solo la stdlib de Python.
- **Backward compatibility:** El sistema existente sigue funcionando sin cambios.
- **Configurable:** Parámetros como timeouts, reintentos y umbrales se pueden ajustar.
