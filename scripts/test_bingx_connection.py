"""
Diagnostico de conexion BingX.
Ejecutar desde la MISMA ubicacion que el .exe para probar la misma lectura de .env.
"""

import os
import sys
from pathlib import Path

# Determinar carpeta base como lo hace el bot
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent.parent  # scripts/ -> raiz

ENV_FILE = BASE_DIR / ".env"

print("=" * 60)
print("DIAGNOSTICO BINGX")
print("=" * 60)
print(f"\n[1] Buscando .env en: {ENV_FILE}")
print(f"[1] Existe? {'SI' if ENV_FILE.exists() else 'NO'}")

if not ENV_FILE.exists():
    print("\n[ERROR] El archivo .env no esta en la carpeta correcta.")
    print(f"   Copia tu .env a: {ENV_FILE}")
    sys.exit(1)

# Cargar .env
from dotenv import load_dotenv
load_dotenv(ENV_FILE)

def _clean(v):
    if v is None: return ""
    v = str(v).strip()
    if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
        return v[1:-1]
    return v

# Leer credenciales de BingX como lo hace el bot
api_key = _clean(os.getenv("BINGX_API_KEY", ""))
secret = _clean(os.getenv("BINGX_SECRET", ""))
enabled = _clean(os.getenv("BINGX_ENABLED", "false")).lower() == "true"

print(f"\n[2] BINGX_ENABLED = {'true' if enabled else 'false'}")
print(f"[2] BINGX_API_KEY  = '{api_key[:8]}...{api_key[-4:]}' (long: {len(api_key)})" if len(api_key) > 8 else f"[2] BINGX_API_KEY  = '{api_key}' (long: {len(api_key)})")
print(f"[2] BINGX_SECRET   = (long: {len(secret)})")

if not api_key or not secret:
    print("\n[ERROR] API Key o Secret vacios. Revisa tu .env")
    sys.exit(1)

if not enabled:
    print("\n[WARN] BINGX_ENABLED=false. Cambia a BINGX_ENABLED=true en tu .env")
    sys.exit(1)

# Probar conexion directa con CCXT
print("\n[3] Probando conexion directa con CCXT async...")
import asyncio
import ccxt.async_support as ccxt_async

async def test_connection():
    try:
        bingx = ccxt_async.bingx({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
            'timeout': 30000,
            'options': {
                'defaultType': 'swap',
                'adjustForTimeDifference': True,
            }
        })

        print("   [3a] Cargando markets...")
        await bingx.load_markets()
        print("   [3a] load_markets() OK")

        print("   [3b] Probando fetch_balance...")
        try:
            balance = await bingx.fetch_balance({'type': 'swap'})
            usdt = balance.get('USDT', {})
            free = usdt.get('free', 'N/A')
            print(f"   [3b] Balance USDT disponible: {free}")
        except Exception as e:
            print(f"   [3b] fetch_balance fallo: {e}")

        print("   [3c] Probando fetch_ticker...")
        try:
            ticker = await bingx.fetch_ticker("BTC/USDT:USDT")
            print(f"   [3c] BTC/USDT:USDT precio: {ticker['last']}")
        except Exception as e:
            print(f"   [3c] fetch_ticker fallo: {e}")

        await bingx.close()
        print("\n[RESULTADO] DIAGNOSTICO COMPLETADO - Conexion OK!")

    except ccxt_async.BadSymbol as e:
        print(f"\n[ERROR] BadSymbol: {e}")
        print("   Prueba con otro simbolo como BTC/USDT")
    except ccxt_async.AuthenticationError as e:
        print(f"\n[ERROR] AuthenticationError: {e}")
        print("\n   Causas posibles:")
        print("   1. La API key no tiene permisos para Futuros/Swap")
        print("   2. La key fue generada para otro tipo de cuenta (Standard vs Perpetual)")
        print("   3. La key expiro o fue revocada")
        print("\n   Solucion: Ve a BingX -> API -> Crea una NUEVA API key")
        print("   Asegurate de seleccionar 'Perpetual Futures' como tipo de cuenta")
    except ccxt_async.NetworkError as e:
        print(f"\n[ERROR] NetworkError: {e}")
        print("   Posible bloqueo de red o firewall")
    except Exception as e:
        print(f"\n[ERROR] Inesperado: {type(e).__name__}: {e}")

asyncio.run(test_connection())
