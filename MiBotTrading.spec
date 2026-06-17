# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('.githooks', '.githooks')],
    hiddenimports=['utils.config', 'utils.helpers', 'utils.translations', 'utils.logger', 'utils.settings_manager', 'utils.config_backup', 'services.exchange_service', 'services.market_data', 'services.notifier', 'services.updater', 'core.manager', 'core.engine', 'core.parser', 'models.data_classes', 'utils.resilience.retry_service', 'utils.resilience.circuit_breaker', 'utils.resilience.decorators', 'utils.resilience.health_monitor'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MiBotTrading',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
