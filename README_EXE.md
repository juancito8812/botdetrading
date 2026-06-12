# MiBotTrading - Ejecutable Portable

## 📋 Requisitos
- **No requiere Python** ni ninguna dependencia adicional
- Solo funciona en **Windows 10/11**

## 🚀 Cómo usar

### Opción 1: Compartir todo (recomendado)
Comparte la carpeta completa que contiene:
1. `MiBotTrading.exe`
2. `.env` (tus credenciales)
3. `config.json` (configuración de riesgo)
4. `canales.json` (canales de Telegram)
5. `posiciones.json` (historial de posiciones)
6. `telegram_session/` (sesión de Telegram - se crea automáticamente)

### Opción 2: Solo el .exe (sin credenciales)
Comparte solo el `MiBotTrading.exe`. El usuario deberá:
1. Crear un `.env` con sus propias credenciales
2. Crear o editar `config.json` con su configuración

## ⚙️ Configuración Inicial
1. **Editar `.env`**: Poner tus API keys de exchanges y Telegram
2. **Editar `config.json`**: Ajustar apalancamiento, porcentajes, etc.
3. **Ejecutar `MiBotTrading.exe`**

## 🖥️ Interfaz
El bot abre una ventana de escritorio con pestañas para:
- **🔐 APIs**: Configurar credenciales de exchanges y Telegram
- **⚖️ Riesgo**: Ajustar apalancamiento, margen, % de capital
- **📢 Canales**: Agregar IDs de canales de Telegram
- **🔌 Test**: Probar conexión con exchanges
- **📊 Posiciones**: Ver historial de operaciones
- **💰 Saldos**: Consultar balances
- **📟 Consola**: Logs en tiempo real

## 🔒 Notas de seguridad
- Las credenciales se guardan en `.env` (mismo directorio que el .exe)
- La sesión de Telegram se guarda en `telegram_session/user_session.session`
- No compartas tu `.env` ni `telegram_session/` con nadie