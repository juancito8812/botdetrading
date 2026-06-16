# Session Handoff -- MiBotTrading

> **Creado:** 13/06/2026
> **Ultima actualizacion:** 15/06/2026 (v14 - Bugfixes C1/C2: Signal serialization + decorators exchange_id)
> **Proposito:** Documento de continuidad para que cualquier IA o agente retome el proyecto exactamente donde lo dejamos. **LEER ESTE ARCHIVO ES OBLIGATORIO AL INICIAR UNA NUEVA SESION.**

---

## REGLA #1: Usar Superpowers SIEMPRE — con TODA IA, en TODA sesion

> **⚠️ REGLA ABSOLUTA: Este proyecto USA SUPERPOWERS. Toda IA — sea Claude, ChatGPT, Codebuff, Cline, Copilot, Gemini, o cualquier otro agente — DEBE seguir este flujo en CADA sesion, sin excepcion.**

> **Cada vez que se inicie una NUEVA sesion o se CAMBIE de agente/modelo de IA, se DEBE cargar el skill `using-superpowers` y seguir el flujo completo. No importa si la IA anterior era Claude y ahora es ChatGPT — el flujo es el MISMO.**

### Flujo obligatorio para TODA IA en TODA sesion:

```
1. 🦸 CARGAR Superpowers      → Al INICIAR cualquier sesion con cualquier IA
                                 (skill: using-superpowers)
2. 📖 LEER contexto           → MEMORY.md + SESSION_HANDOFF.md + git log --oneline -5
3. 🧠 BRAINSTORMING           → Antes de cualquier cambio creativo o implementacion
4. 📄 WRITING SPECS           → Documentar en docs/superpowers/specs/
5. 📋 WRITING PLANS           → Para tareas de 3+ pasos en docs/superpowers/plans/
6. ⚡ SUBAGENT DEVELOPMENT    → Ejecutar con agentes especializados
7. 👀 CODE REVIEW             → Revisar cambios antes de finalizar
8. ✅ VERIFICATION            → Tests + cobertura + calidad
9. 📝 ACTUALIZAR docs         → MEMORY.md + SESSION_HANDOFF.md + README si aplica
```

> **🔴 Esto aplica a: Claude, ChatGPT, Codebuff, Cline, Copilot, Gemini, y cualquier otro agente/IA que toque este proyecto. La metodologia Superpowers es el contrato de calidad del proyecto. Ignorarla = cambios inconsistentes y perdida de contexto entre sesiones.**

> **💡 Si eres una IA leyendo esto: DETENTE. Carga el skill `using-superpowers` AHORA antes de continuar. No asumas que otra IA ya lo hizo por ti.**

---

## Resumen Rapido

**Proyecto:** Bot de trading automatizado que recibe senales via Telegram y ejecuta ordenes LONG/SHORT en exchanges de criptomonedas (Bitget, BingX).

**Stack:** Python 3.14, Tkinter (GUI), CCXT async (exchanges), Telethon (Telegram), asyncio, pytest, PyInstaller

**Ultima release:** `v1.2.0` -- StringSession + revert TG Scraping
**Ultimo .exe:** `dist/MiBotTrading.exe` (61 MB, con auto-updater + bugfixes C1/C2)
**Tests:** 365/365 pasando (92% cobertura real)
**Sesion Telegram:** StringSession (sin SQLite, sin file locking)
**Auto-Updater:** check + download + apply via GitHub Releases + UI en Settings
**Bugfix C1:** Signal dataclass serialization (pending_limits.json ya no crashea)
**Bugfix C2:** Decoradores exchange_id (args[0]=self corregido)
**Superpower docs:** `docs/superpowers/specs/2026-06-15-auto-updater.md`
**Pre-commit hook:** `.githooks/pre-commit` valida MEMORY.md + SESSION_HANDOFF.md
**.exe:** Compilado con `--noconsole` (sin ventana negra)
**GitHub:** https://github.com/juancito8812/botdetrading.git
**Actions:** https://github.com/juancito8812/botdetrading/actions

**Commits recientes (origin/master):**
| Commit | Descripcion |
|--------|-------------|
| (pendiente) | feat: auto-updater + fix C1/C2: Signal serialization + decorators exchange_id |
| `e6d693e` | fix: StringSession para Telegram + revert TG Scraping + fix await |
| `a1194df` | Revert 'feat: TG Scraping toggleable en settings' |
| `d28386f` | fix: log rotation 1 mes + bugs corregidos (engine.py, notifier.py) |
| `19cd294` | build: actualizar MiBotTrading.spec con --noconsole |

---

## Ultimas Sesiones (15/06/2026)

### 1-14. (Sesiones anteriores documentadas en versiones previas)

### 15. Tooltips de ayuda + Notificaciones seleccionables (commit `364e9de`)

Ver sesion #14 en version v7 del documento.

### 16. Dashboard auto-refresh + Auto-start Windows + Fix pack/grid (commit `364e9de`)

(Ver sesion #14 en version v8 del documento)

---

### 17. Superpowers obligatorio + Refactor manager.py + Cleanup + pre-commit hook + .exe sin consola (15/06/2026)

**Que se hizo:** Lima gruesa de calidad y documentacion:

#### Refactor de manager.py (commit `b108f8b`)
- Extraidos 5 metodos de `save()` y `load()` (`_check_pending_recovery`, `_create_save_checkpoint`, `_write_positions`, `_finalize_save`, `_load_positions_from_data`)
- `save()` reducido de ~35 a ~8 lineas de orquestacion
- Codigo muerto eliminado en `retry_service.py` (raise inalcanzable)

#### Intento de cobertura 100% (quedo en 97%)
- 85 tests nuevos (total 503), coverage de 91% a 97%
- engine.py subio de 85% a 93%
- La mayoria de tests eran duplicados -- eliminados en cleanup

#### Cleanup de tests duplicados y archivos temporales
- Eliminados 3 archivos de test duplicados: `test_coverage_fixes.py`, `test_coverage_engine_final.py`, `test_engine_coverage_v2.py`
- Eliminados: `build/`, `MiBotTrading.spec` (viejo), `.coverage`, `.pytest_cache/`, `logs/`, `recovery/`, `resilience/`, artefactos
- Tests reales: 365 (no 503 inflado)

#### .gitignore actualizado
- Agregadas categorias: Python (`*.py[cod]`, `*.egg-info/`), PyInstaller (`build/`, `*.spec`), Tests (`.pytest_cache/`), Logs (`*.log`), IDE (`.idea/`, `*.swp`), Sistema (`.DS_Store`, `Thumbs.db`)

#### Compilacion .exe
- `dist/MiBotTrading.exe` compilado 2 veces (primero normal, luego con `--noconsole`)
- Version final: **sin ventana negra** al abrirse

#### Documentacion Superpowers reforzada
- README.md, MEMORY.md, SESSION_HANDOFF.md actualizados con regla absoluta:
  "Toda IA -- Claude, ChatGPT, Codebuff, Cline, Copilot, Gemini -- DEBE seguir Superpowers en CADA sesion"
- Flujo de 9 pasos documentado en los 3 archivos

#### Pre-commit hook creado
- Nuevo: `.githooks/pre-commit`
- Valida que MEMORY.md y SESSION_HANDOFF.md esten actualizados cuando se commiten archivos de codigo
- No bloquea el commit, pero muestra advertencia clara
- Configurado via `git config core.hooksPath .githooks`
- Incluido en el build del .exe como `--add-data`

#### Commits realizados
| Commit | Mensaje |
|--------|---------|
| `19cd294` | `build: actualizar MiBotTrading.spec con --noconsole` |
| `dba82a7` | `docs: Superpowers obligatorio + pre-commit hook` |
| `b108f8b` | `refactor: engine.py + manager.py + cleanup + .gitignore` |

**Archivos modificados/creados:**
| Archivo | Cambio |
|---------|--------|
| `core/manager.py` | Refactor: 5 metodos extraidos |
| `utils/resilience/retry_service.py` | Codigo muerto eliminado |
| `tests/test_engine.py` | Tests ampliados (trailing, breakeven) |
| `.gitignore` | Completado con Python, PyInstaller, Tests, IDE, Sistema |
| `.githooks/pre-commit` | **Nuevo** -- hook Superpowers |
| `README.md` | Superpowers reforzado como regla absoluta |
| `MEMORY.md` | Nueva seccion Superpowers Framework |
| `SESSION_HANDOFF.md` | REGLA #1 expandida para cada IA distinta |
| `MiBotTrading.spec` | Actualizado con --noconsole |
| `dist/MiBotTrading.exe` | Recompilado sin consola (61 MB) |

**Tests:** 365/365 pasando (92% cobertura real)
**.exe:** `dist/MiBotTrading.exe` (modo --noconsole, incluye .githooks + hidden-import tg_scraper)

---

### 18. TG Scraping toggleable + Log rotation 1 mes + Bugfixes (15/06/2026)

> ⚠️ **NOTA:** Commit `d4d26a2` (TG Scraping toggle) fue revertido en `a1194df`. El TG Scraping ya NO existe en el codigo. Log rotation y bugfixes de engine/notifier se conservan (commit `d28386f`).

---

### 19. Fix: Telegram database is locked + event loop conflict (15/06/2026)

**Primer intento (evolucion de fixes en main.py):**

| Intento | Fix | Resultado |
|---------|-----|-----------|
| 1 | WAL mode + busy_timeout SQLite | ❌ Stale .wal/.shm files causaban lock igual |
| 2 | Eliminar archivos stale antes de conectar | ❌ BD .session corrupta de crashes previos |
| 3 | **StringSession** (sin SQLite) | ✅ **SOLUCION DEFINITIVA** |

**Solucion final - StringSession:**
- `from telethon.sessions import StringSession` — sesion en memoria, sin SQLite
- `_create_telegram_client()`: usa `StringSession(session_data)` en lugar de archivo `.session`
- `_save_telegram_session()`: serializa la sesion a texto y la guarda en `user_session.string`
- Se llama despues de autenticacion exitosa para persistir la sesion
- Al reconectar, carga la sesion desde el archivo `.string`
- **No hay archivos `.session`, `.session-wal`, `.session-shm`** → imposible el `database is locked`

**Bugfix adicional - await a metodo sincronico:**
- `_save_telegram_session()` es un metodo sincronico (`def`, no `async def`) pero se llamaba con `await`
- Causaba: `TypeError: 'NoneType' object can't be awaited` justo despues de autenticar
- Fix: `self._save_telegram_session()` (sin `await`)

**Los fixes de concurrencia (lock threading, stop_bot, cleanup) se conservan** de los intentos anteriores.

---

### 20. Auto-Updater via GitHub Releases + UI en Settings (15/06/2026)

**Superpower docs creados:**
- `docs/superpowers/specs/2026-06-15-auto-updater.md`
- `docs/superpowers/plans/2026-06-15-auto-updater.md`

**Arquitectura:**
```
1. CHECK  → GET api.github.com/.../releases/latest, compara tag con version local
2. DOWNLOAD → Descarga .exe del release a updates/
3. APPLY → Crea .bat que espera 3s, reemplaza .exe, inicia nuevo, se autoelimina
```

**Archivos creados:**
| Archivo | Descripcion |
|---------|-------------|
| `VERSION` | Version actual (`v1.2.0`) |
| `services/updater.py` | Servicio completo: check, download, .bat apply |

**Archivos modificados:**
| Archivo | Cambio |
|---------|--------|
| `utils/translations.py` | Claves `upd_*` en ES y EN (13 claves) |
| `utils/settings_manager.py` | `auto_check_updates: True` en defaults |
| `ui/main_window.py` | Seccion Updates en Settings (version, check, download, release notes) |
| `main.py` | Auto-check 3s despues del inicio en background thread |

**Funcionalidad:**
| Feature | Detalle |
|---------|--------|
| Check manual | Boton en Settings > Actualizaciones, corre en hilo separado |
| Auto-check startup | 3s despues de cargar GUI, configurable via checkbox |
| Release notes | Widget de texto con notes de la version (oculto hasta que hay disponible) |
| Download | Streaming 8KB chunks, log cada 10%, timeout 120s |
| Apply .bat | Crea script que espera 3s, copia .exe, inicia nuevo, se autoelimina |
| Soporte .zip | Extrae con PowerShell Expand-Archive si el asset es .zip |
| Solo .exe mode | No funciona en modo desarrollo (script Python) — require sys.frozen |

**Tests:** 365/365 pasando
**.exe compilado:** `dist/MiBotTrading.exe` (61 MB) con `--hidden-import=services.updater`

**Comportamiento en UI:**
- Label con version actual al abrir Settings
- Check "Buscar actualizaciones al iniciar" (persiste en settings.json)
- Boton "🔄 Buscar actualizaciones" (deshabilitado durante la busqueda)
- Boton "📥 DESCARGAR" (habilitado solo cuando hay nueva version)
- Status: checking / up-to-date / nueva version disponible / error
- Release notes en widget de texto (aparece solo cuando hay nueva version)
- Al hacer clic en DESCARGAR: download → .bat → root.quit() → .bat reemplaza y reinicia

---

### 21. Bugfixes: Signal serialization (C1) + Decorators exchange_id (C2) (15/06/2026)

**C1 — Signal dataclass → JSON serialization crash** (`core/engine.py`)
- `_pending_limit_orders` guardaba objeto `Signal` directamente, `json.dump()` crasheaba
- Fix: `_signal_to_dict()` y `_signal_from_dict()` para serialización/reconstrucción
- `_save_pending_limits()` convierte Signal→dict antes de guardar, con `default=str`
- `_load_pending_limits()` reconvierte dict→Signal al cargar desde disco
- `_place_limit_entry()` y `_place_dca_orders()` guardan signal_dict
- `_process_filled_limit_order()` detecta si signal es dict y lo reconvierte

**C2 — args[0] = self en decoradores** (`utils/resilience/decorators.py`)
- Los 4 decoradores (retry, circuit_breaker, circuit_breaker_dynamic, log_errors) usaban `args[0]` como exchange_id
- En métodos bound de ExchangeService, `args[0]` es `self` (la instancia), no el exchange_id
- Fix: nueva función helper `_extract_exchange_id(args, kwargs)` que busca kwargs primero, luego recorre args para el primer string
- Ahora `get_balance(self, "bingx")` extrae "bingx" correctamente

**Test fix:**
- El fixture `engine` ahora limpia `_PENDING_LIMITS_FILE` en disco entre tests
- Antes los tests dejaban datos persistentes que el siguiente test cargaba (porque C1 ahora sí serializa correctamente)

**Archivos modificados:**
| Archivo | Cambio |
|---------|--------|
| `core/engine.py` | C1: _signal_to_dict, _signal_from_dict, save/load fixes |
| `utils/resilience/decorators.py` | C2: _extract_exchange_id en 4 decoradores |
| `tests/test_engine.py` | Fixture engine limpia pending_limits entre tests |

**Tests:** 365/365 pasando
**.exe compilado:** `dist/MiBotTrading.exe` (61 MB)

---

## GitHub Actions -- Workflows

| Workflow | Trigger | Stack | Que hace |
|----------|---------|-------|----------|
| **Tests** (`tests.yml`) | Push/PR a master | Ubuntu, Python 3.10/3.11/3.12 | pip install + pytest tests/ -v |
| **Lint** (`lint.yml`) | Push/PR a master | Ubuntu, Python 3.11 | flake8 + mypy |
| **Build** (`build.yml`) | Tags v* o manual | Windows-latest | PyInstaller -> .exe -> Release |

**Nota:** Checkout configurado con `submodules: false` para evitar errores del submodulo superpowers/.

---

## Como verificar el estado

```bash
# Tests completos (365 tests - 92% cobertura)
python -m pytest tests/ -v

# Cobertura local
python -m pytest tests/ --cov=core --cov=models --cov=services --cov=utils --cov-report=term

# Estado de git
git status
git log --oneline -5

# Verificar que el pre-commit hook esta activo
git config core.hooksPath

# Ver workflows en GitHub
# https://github.com/juancito8812/botdetrading/actions
```

---

## Proximos Pasos / TODOs

Priorizados por impacto:

1. **Activar mas exchanges** -- Binance, Bybit, OKX (ya configurados, solo falta habilitar en `.env` y probar)
2. **Llegar a 100% cobertura real** -- Actualmente 92%, engine.py es el mayor reto (~55 lineas en guard clauses)
3. **Tests unitarios del updater** -- services/updater.py no tiene tests dedicados
4. **Graficos en pestana Reportes** -- Agregar matplotlib para visualizar PnL historico

---

## Configuracion Actual

| Parametro | Valor |
|-----------|-------|
| Apalancamiento | 5x |
| Modo margen | Cross |
| Cantidad minima | 2.0 USDT |
| Entrada | Auto (desviacion max 3%) |
| DCA | 3 partes |
| Trailing stop | Activacion 1.5%, distancia 0.8% |
| Timeout orden LIMIT | 10 min |
| Auto-start Windows | Activado por defecto |
| Dashboard auto-refresh | 60s (activado por defecto) |
| Notificaciones | Seleccionables desde UI (8 tipos) |
| Auto-Updater | Check startup + manual, download, apply .bat |
| Check interval health | 60s |
| Retry intentos | 3 (backoff exp. 1s->2s->4s) |
| Circuit breaker | 5 fallos -> OPEN 60s -> HALF_OPEN |
| Backup rotacion | 24 backups comprimidos (gzip) |

---

## Superpowers Framework

Framework de metodologia de desarrollo instalado (14 skills). Los skills estan en `.agents/skills/` y se activan automaticamente.

**Flujo de trabajo:** brainstorming -> writing-plans -> subagent-driven-development (con revision spec + code quality)

**Documentos de diseno y plan en:** `docs/superpowers/specs/` y `docs/superpowers/plans/`

---

## Notas Importantes

- **Credenciales excluidas de git:** `.env`, `config.json`, `canales.json` -- estan en `.gitignore`
- **Pre-commit hook:** `.githooks/pre-commit` valida MEMORY.md + SESSION_HANDOFF.md. Instalar con: `git config core.hooksPath .githooks`
- **Superpowers obligatorio para TODA IA:** Leer REGLA #1 al inicio de este documento
- **.exe sin consola:** `dist/MiBotTrading.exe` compilado con `--noconsole` — no muestra ventana negra
- **Auto-start Windows:** Se crea tarea en el Programador de Tareas al primer arranque (idempotente)
- **Bot auto-inicia:** Si hay credenciales, el bot arranca solo al abrir la app (500ms delay)
- **Dashboard auto-refresh:** Carga datos a los 1s de abrir, luego refresca cada 60s
- **Para activar notificaciones:** Configurar desde UI en pestana Telegram -> Chat ID / checkboxes
- **Para empezar una nueva sesion:** Leer este archivo + `.agents/MEMORY.md` + `git log --oneline -3`
