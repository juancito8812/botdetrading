# Spec: Export/Import de Configuración Cifrada

**Fecha**: 2026-06-14
**Estado**: Aprobado

## Resumen

Agregar en la pestaña Ajustes una sección "Respaldo de Configuración" que permita exportar toda la configuración del bot (API keys, risk config, canales, settings) a un archivo `.botconfig` cifrado con contraseña, e importarlo para restaurar todos los datos.

## Datos incluidos

| Origen | Función de carga | Función de guardado |
|--------|------------------|---------------------|
| `.env` | `load_api_creds()` | `save_api_creds()` |
| `config.json` | `load_risk_config()` | `save_risk_config()` |
| `canales.json` | `load_channels()` | `save_channels()` |
| `settings.json` | `load_settings()` | `save_settings()` |

## Estructura del archivo `.botconfig`

```json
{
  "version": 1,
  "exported_at": "2026-06-14T15:30:00",
  "data": {
    "apis": { ... },
    "risk": { ... },
    "channels": [...],
    "settings": { ... }
  }
}
```

## Cifrado

- Algoritmo: AES simétrico via `cryptography.fernet.Fernet`
- Derivación de clave: PBKDF2HMAC con SHA256, 100k iteraciones, salt aleatorio
- Almacenamiento: salt (16 bytes) + token cifrado concatenados
- Se usa `filedialog.asksaveasfilename` / `askopenfilename` para elegir ubicación

## UI en pestaña Ajustes

Nuevo LabelFrame "Respaldo de Configuración" debajo de Auto-start:

```
┌─ 💾 RESPALDO DE CONFIGURACIÓN ──────────────────┐
│                                                   │
│  [📤 Exportar configuración]                     │
│  [📥 Importar configuración]                     │
│                                                   │
│  Exporta API keys, riesgo, canales y ajustes      │
│  en un archivo .botconfig cifrado.                │
└───────────────────────────────────────────────────┘
```

## Archivos a modificar/crear

| Archivo | Cambio |
|---------|--------|
| `utils/config_backup.py` | **Nuevo**: lógica de cifrado/descifrado, export/import |
| `utils/translations.py` | +12 claves nuevas (es/en) |
| `ui/main_window.py` | Nueva sección en `setup_settings_tab()` + handlers |
| `requirements.txt` | Agregar `cryptography` |

## Flujo de exportación

1. Usuario click → `_export_config()`
2. `filedialog.asksaveasfilename(defaultextension=".botconfig")`
3. Popup pide contraseña (Entry con show="*", confirmar)
4. `config_backup.export_config(password, filepath)` → recopila, cifra, guarda
5. Messagebox éxito

## Flujo de importación

1. Usuario click → `_import_config()`
2. `filedialog.askopenfilename(filetypes=[("Bot Config","*.botconfig")])`
3. Popup pide contraseña (Entry con show="*")
4. `config_backup.import_config(password, filepath)` → descifra, valida, restaura
5. Messagebox éxito + indicación de reiniciar
