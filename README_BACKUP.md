# Respaldo del Bot de Trading Refactorizado

## Archivos originales (copia de seguridad)

El archivo `bot_unificado v2.py` original (1654 lineas) fue dividido en modulos:

| Archivo | Lineas | Contenido |
|---------|--------|-----------|
| `config.py` | ~260 | Constantes, globals, helpers, DNS patch, reconexion |
| `exchange.py` | ~250 | ExchangeAdapter, crear_cliente_ccxt_async, safe_close |
| `positions.py` | ~520 | Position, PositionManager, utilidades de trading |
| `signals.py` | ~50 | parsear_senal |
| `gui.py` | ~710 | InterfazConfiguracion, GuiHandler, exchanges_activos |
| `main.py` | ~120 | run_bot(), bot_principal, entry point |
| `bot_unificado v2.py` | ~20 | Launcher (importa y ejecuta main.run_bot()) |

## Dependencias entre modulos

    config -> exchange -> positions -> signals -> gui -> main

## Como restaurar

Los archivos en `backup_modulos/` y `bot_unificado_backup.zip` contienen
copias exactas de todos los modulos al momento de la refactorizacion.
Para restaurar, solo copia los archivos de vuelta al directorio raiz.

## Como consultar funciones especificas

Busca por nombre de funcion dentro de los modulos:
- Funciones de configuracion: config.py
- Clientes de exchange: exchange.py
- Posiciones y trading: positions.py
- Parseo de senales: signals.py
- Interfaz grafica: gui.py
- Orquestacion: main.py
