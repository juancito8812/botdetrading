import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
import ccxt.async_support as ccxt_async
import logging
import traceback

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BASE_DIR / '.env'

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_ccxt')

load_dotenv(ENV_FILE)

EXCHANGES = ['bitget', 'bingx']

async def test_exchange(ex):
    try:
        api_key = os.getenv(f"{ex.upper()}_API_KEY", '')
        secret = os.getenv(f"{ex.upper()}_SECRET", '')
        passphrase = os.getenv(f"{ex.upper()}_PASSPHRASE", '')
        config = {
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
            'timeout': 20000,
        }
        if passphrase:
            config['password'] = passphrase
        cls = getattr(ccxt_async, ex)
        exchange = cls(config)
        try:
            logger.info(f"Loading markets for {ex}...")
            await exchange.load_markets()
            logger.info(f"OK: {ex} markets loaded. {len(exchange.markets)} markets available")
        finally:
            await exchange.close()
    except Exception as e:
        logger.error(f"Failed to init {ex}: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())

async def main():
    for ex in EXCHANGES:
        await test_exchange(ex)

if __name__ == '__main__':
    asyncio.run(main())
