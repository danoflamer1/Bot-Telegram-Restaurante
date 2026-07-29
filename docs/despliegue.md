# Manual de Despliegue e Instalación
Este documento detalla el procedimiento paso a paso para desplegar e instalar el sistema MVP Restaurante (Bot de Telegram) en un entorno limpio, garantizando la correcta ejecución de la base de datos y los servicios del bot.

---

## 1. Requisitos Previos del Sistema
Antes de iniciar la instalación, asegúrese de que el entorno cumpla con las siguientes dependencias del sistema:

- **Sistema Operativo:** Linux (Ubuntu 20.04+ / Debian 11+), macOS o Windows 10/11.
- **Python:** Versión 3.10 o superior instalada.
- **Git:** Para la clonación del repositorio.
- **Cuenta de Telegram:** Con acceso a `@BotFather` para la obtención del Token API del bot.

---

## 2. Obtención del Token de Telegram (BotFather)
1. Abra la aplicación de Telegram y busque el usuario oficial `@BotFather`.
2. Envíe el comando `/newbot`.
3. Asigne un nombre al bot (ejemplo: `Restaurante MVP Bot`).
4. Asigne un nombre de usuario único terminado en `bot` (ejemplo: `MiRestaurante_MVP_bot`).
5. `BotFather` le devolverá un Token de acceso a la API HTTP (formato parecido a `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).

---

## 3. Configuración del Token en el Código Fuente
El proyecto gestiona la clave de acceso del bot directamente en el archivo ejecutable `run_bot.py`.

1. Abra el archivo `run_bot.py` ubicado en la raíz del proyecto.
2. Busque la variable donde se asigna el token del bot (o reemplace la cadena existente por su nuevo token):

```python
# run_bot.py
TOKEN = "TU_TOKEN_DE_BOTFATHER_AQUI"
```

3. Guarde los cambios en el archivo `run_bot.py`.

---

## 4. Guía de Instalación Paso a Paso

### Paso 1: Clonar el Repositorio
Abra una terminal y clone el repositorio oficial en su equipo local:

```bash
git clone https://github.com/danoflamer1/Bot-Telegram-Restaurante.git
cd Bot-Telegram-Restaurante
```

### Paso 2: Crear y Activar el Entorno Virtual Python
Se utiliza el módulo estándar `venv` para aislar las dependencias dentro de la carpeta `venv`:

**En Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**En Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**En Windows (CMD):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

### Paso 3: Instalar Dependencias del Proyecto
Con el entorno virtual `venv` activo, instale las librerías necesarias especificadas en `requirements.txt`:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 5. Población Inicial de la Base de Datos
Antes de ejecutar el bot por primera vez, se deben crear las tablas en SQLite (`restaurante.db`) e insertar los datos iniciales (usuarios administradores, repartidores de prueba y catálogo inicial de platillos con imágenes).

Ejecute el módulo poblador mediante el siguiente comando:

```bash
python -m app.core.poblador
```

**Resultado esperado:**
```text
[INFO] Se agregaron platillos de prueba.
```

---

## 6. Ejecución y Puesta en Marcha del Sistema
Una vez configurado el token en `run_bot.py` e inicializada la base de datos, inicie el proceso principal del bot mediante:

```bash
python run_bot.py
```

## 7. Verificación del Despliegue
- **Cliente:** Busque su bot en Telegram y envíe `/start`. Deberá recibir el mensaje de bienvenida y el teclado con el botón `🍔 Ver Menú`.
- **Administrador:** Verifique que la cuenta registrada como `ADMINISTRADOR` reciba las notificaciones de nuevos comprobantes de pago y pueda usar `🍔 Gestionar Menú`.
- **Repartidor:** Ingrese desde la cuenta del repartidor registrado y ejecute `/pedidos_pendientes` o presione `🛵 Pedidos Pendientes`.

---

## 8. Solución de Problemas Comunes (Troubleshooting)

- **Error: `Unauthorized` al iniciar el bot:**
  - *Causa:* El token asignado en `run_bot.py` es incorrecto o fue revocado por `BotFather`.
  - *Solución:* Revisa el token generado en `@BotFather` y asegúrate de pegarlo correctamente dentro de `run_bot.py`.

- **Error: `OperationalError: no such table`:**
  - *Causa:* La base de datos no se ha inicializado o el archivo `restaurante.db` no existe.
  - *Solución:* Ejecute de nuevo el script poblador: `python -m app.core.poblador`.

- **Error al descargar/mostrar imágenes de los platos o comprobantes:**
  - *Causa:* No existen los directorios de almacenamiento en `/docs`.
  - *Solución:* Asegúrese de que las carpetas `docs/platos/` y `docs/comprobantes/` existan y tengan permisos de lectura y escritura.