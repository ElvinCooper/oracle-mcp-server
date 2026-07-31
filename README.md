# oracle-mcp-server

Servidor MCP (Model Context Protocol) en Python para conectar a **Oracle 11g**
usando `python-oracledb` en **modo thick** (obligatorio en 11g, ya que el modo
thin del driver solo soporta Oracle 12.1+). Pensado para usarse desde
[opencode](https://opencode.ai) u otro cliente MCP compatible con servidores
locales (stdio).

**Soporta múltiples conexiones a Oracle** y funciona con cualquier cliente MCP: opencode, Claude Code, Cursor, Codex, Continue.dev, etc.

## ⚡ Quick Start (puesta en marcha rápida)

```powershell
# 1. Clonar o copiar el proyecto
cd C:\ruta\oracle-mcp-server

# 2. Ejecutar setup (crea .venv, instala dependencias, copia .env)
.\setup.ps1

# 3. Editar .env con tus credenciales Oracle
notepad .env

# 4. Iniciar el servidor
.\.venv\Scripts\oracle-mcp
```

Si ves `Pool '<nombre>' listo` en la salida, ya está funcionando.

**Requisitos:** Python 3.10+ y Oracle Instant Client instalado.

---

## Tools expuestas

| Tool | Descripción |
|---|---|
| `list_tables` | Lista tablas de un schema (o del usuario actual) |
| `describe_table` | Devuelve columnas, tipo de dato, nulabilidad, longitud |
| `run_query` | Ejecuta un `SELECT` de solo lectura, con límite de filas |
| `execute_statement` | Ejecuta `INSERT/UPDATE/DELETE/DDL`, **deshabilitado por defecto** |
| `list_connections` | Lista todas las conexiones a Oracle disponibles |

**Parámetro `connection`:** Todas las tools anteriores (excepto
`list_connections`) aceptan un parámetro opcional `connection` para especificar
a qué base de datos conectar. Si no se especifica, usa la primera conexión de
la lista (conexión por defecto).

**Parámetros adicionales:**

- `list_tables(schema, connection)`: `schema` es el owner en mayúsculas (ej.
  `VENTAS`); si se omite, lista las tablas del usuario actual.
- `describe_table(table_name, schema, connection)`: `schema` indica el owner si
  la tabla pertenece a otro usuario.
- `run_query(sql, max_rows, connection)`: `max_rows` limita las filas devueltas
  en la llamada (por defecto usa el `_MAX_ROWS` de la conexión). El resultado
  incluye `row_count`, `truncated` (si quedaron filas sin devolver) y
  `limit_applied`.

### Seguridad por diseño

- Por defecto **solo lectura**: `run_query` valida que la sentencia empiece
  con `SELECT`/`WITH` y rechaza múltiples sentencias separadas por `;`.
- `execute_statement` está bloqueada salvo que definas
  `ORACLE_CONN_<NOMBRE>_ALLOW_WRITE=true` (o `ORACLE_ALLOW_WRITE=true` en el
  modo legacy) en el entorno **y** pases `confirm=true` en la llamada (doble
  seguro).
- Las credenciales viven en variables de entorno, nunca hardcodeadas.

## 1. Requisitos previos

- Python 3.10+
- Oracle Instant Client ya instalado (dijiste que ya lo tienes disponible).
  Necesitas la ruta del directorio con `libclntsh.so` (Linux/Mac) o
  `oci.dll` (Windows), por ejemplo `/opt/oracle/instantclient_11_2`.
- Acceso de red al listener de Oracle (host:puerto) y un SID o service_name.

## 2. Instalación

### Automática (Windows)

```powershell
cd C:\ruta\oracle-mcp-server
.\setup.ps1
```

### Manual (Windows / Linux / Mac)

```bash
cd oracle-mcp-server
python3 -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows
pip install -e .
```

## 3. Configuración

### Opción A: Múltiples conexiones (Recomendado)

Copia `.env.example` a `.env` y completa tus datos:

```bash
cp .env.example .env
```

Formato para múltiples conexiones:

```bash
# Lista de conexiones (nombres separados por comas)
ORACLE_CONNECTIONS=facturacion,clinica

# Conexion "facturacion"
ORACLE_CONN_FACTURACION_USER=mi_usuario
ORACLE_CONN_FACTURACION_PASSWORD=mi_password
ORACLE_CONN_FACTURACION_HOST=192.168.1.10
ORACLE_CONN_FACTURACION_PORT=1521
ORACLE_CONN_FACTURACION_SID=ORCL
ORACLE_CONN_FACTURACION_CLIENT_LIB_DIR=/opt/oracle/instantclient_11_2
ORACLE_CONN_FACTURACION_ALLOW_WRITE=false
ORACLE_CONN_FACTURACION_MAX_ROWS=200

# Conexion "clinica"
ORACLE_CONN_CLINICA_USER=clinica_user
ORACLE_CONN_CLINICA_PASSWORD=clinica_pass
ORACLE_CONN_CLINICA_HOST=192.168.1.20
ORACLE_CONN_CLINICA_PORT=1521
ORACLE_CONN_CLINICA_SID=ORCL
ORACLE_CONN_CLINICA_CLIENT_LIB_DIR=/opt/oracle/instantclient_11_2
```

### Opción B: Una sola conexión (Legacy - Retrocompatible)

Si `ORACLE_CONNECTIONS` no está definido, el servidor busca variables legacy:

```bash
ORACLE_USER=mi_usuario
ORACLE_PASSWORD=mi_password
ORACLE_HOST=192.168.1.10
ORACLE_PORT=1521
ORACLE_SID=ORCL
ORACLE_CLIENT_LIB_DIR=/opt/oracle/instantclient_11_2
ORACLE_ALLOW_WRITE=false
ORACLE_MAX_ROWS=200
```

### Variables por conexión

| Variable | Descripción | Default |
|---|---|---|
| `ORACLE_CONN_<NOMBRE>_USER` | Usuario de Oracle | (requerido) |
| `ORACLE_CONN_<NOMBRE>_PASSWORD` | Contraseña | (requerido) |
| `ORACLE_CONN_<NOMBRE>_HOST` | Host del servidor | (requerido) |
| `ORACLE_CONN_<NOMBRE>_PORT` | Puerto | 1521 |
| `ORACLE_CONN_<NOMBRE>_SID` | SID de Oracle | - |
| `ORACLE_CONN_<NOMBRE>_SERVICE_NAME` | Service name | - |
| `ORACLE_CONN_<NOMBRE>_CLIENT_LIB_DIR` | Ruta al Instant Client | - |
| `ORACLE_CONN_<NOMBRE>_ALLOW_WRITE` | Habilitar escritura | false |
| `ORACLE_CONN_<NOMBRE>_MAX_ROWS` | Límite de filas por query | 200 |
| `ORACLE_CONN_<NOMBRE>_CONNECT_TIMEOUT` | Timeout conexión (seg) | 10 |
| `ORACLE_CONN_<NOMBRE>_POOL_MIN` | Mínimo conexiones en pool | 1 |
| `ORACLE_CONN_<NOMBRE>_POOL_MAX` | Máximo conexiones en pool | 4 |

### Convención de Nombres de Variables

**Regla de oro:** El nombre de la conexión en `ORACLE_CONNECTIONS` define los
nombres de todas las variables de entorno asociadas.

| Paso | Ejemplo |
|------|---------|
| Nombre en `ORACLE_CONNECTIONS` | `afp_pruebas` |
| Convertir a MAYÚSCULAS | `AFP_PRUEBAS` |
| Agregar prefijo | `ORACLE_CONN_AFP_PRUEBAS` |
| Agregar sufijo | `ORACLE_CONN_AFP_PRUEBAS_USER` |

```
ORACLE_CONNECTIONS: "facturacion,afp_pruebas"
        ↓                          ↓
"facturacion"               "afp_pruebas"
        ↓                          ↓
ORACLE_CONN_FACTURACION_*   ORACLE_CONN_AFP_PRUEBAS_*
```

### Convención Recomendada para Nombres

Para mantener consistencia y facilitar el mantenimiento:

| Tipo de Base | Ejemplo de Nombre | Variable |
|--------------|-------------------|----------|
| Producción | `produccion` | `ORACLE_CONN_PRODUCCION_*` |
| Desarrollo | `desarrollo` | `ORACLE_CONN_DESARROLLO_*` |
| Pruebas | `pruebas` | `ORACLE_CONN_PRUEBAS_*` |
| Por área funcional | `facturacion` | `ORACLE_CONN_FACTURACION_*` |

**Recomendaciones:**
- Usar **snake_case** (minúsculas con guión bajo): `mi_conexion`
- **Sin espacios**: `afp_pruebas` en lugar de `AFP Pruebas`
- **Nombres descriptivos**: que indiquen el propósito de la conexión
- **Evitar caracteres especiales**: solo letras, números y guión bajo

### Fuentes de Variables de Entorno

Las variables pueden provenir de múltiples fuentes (por orden de prioridad):

1. **opencode.jsonc** `environment` block (mayor prioridad)
2. **Variables del sistema Windows** (persistente)
3. **Archivo `.env`** (cargado automáticamente por python-dotenv)

**Recomendación de seguridad:** No incluir credenciales en `opencode.jsonc`.
Usar variables del sistema Windows para datos sensibles:

```powershell
# PowerShell - Configurar una vez
[Environment]::SetEnvironmentVariable("ORACLE_CONN_FACTURACION_USER", "mi_usuario", "User")
[Environment]::SetEnvironmentVariable("ORACLE_CONN_FACTURACION_PASSWORD", "mi_password", "User")
```

## 4. Probarlo de forma independiente

Puedes levantar el servidor manualmente para verificar que conecta:

```bash
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows
python -m oracle_mcp.server
```

O usando el entry point directo (disponible después de `pip install -e .`):

```bash
oracle-mcp                       # si el venv está activo
# o desde la ruta absoluta:
.venv/Scripts/oracle-mcp         # Windows
.venv/bin/oracle-mcp             # Linux/Mac
```

Si ves en el log `Pool '<nombre>' listo`, la conexión en thick
mode funcionó. El proceso queda esperando mensajes MCP por stdio (Ctrl+C
para salir).

## 5. Integración con clientes MCP

El servidor se comunica por **STDIO** (estándar en MCP para procesos locales).
Cada cliente MCP tiene su propia configuración; aquí están las más comunes.

> **Importante:** Usa siempre la ruta **absoluta** al Python del `.venv` (así el
> cliente no depende de que el venv esté activado).

### opencode

Define el servidor en el bloque `mcp` de `opencode.json` (o `~/.config/opencode/opencode.jsonc`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "oracle": {
      "type": "local",
      "command": [
        "C:/ruta/completa/oracle-mcp-server/.venv/Scripts/python",
        "-m",
        "oracle_mcp.server"
      ],
      "enabled": true,
      "environment": {
        "ORACLE_CONNECTIONS": "facturacion,clinica",
        "ORACLE_CONN_FACTURACION_USER": "mi_usuario",
        "ORACLE_CONN_FACTURACION_PASSWORD": "mi_password",
        "ORACLE_CONN_FACTURACION_HOST": "192.168.1.10",
        "ORACLE_CONN_FACTURACION_PORT": "1521",
        "ORACLE_CONN_FACTURACION_SID": "ORCL",
        "ORACLE_CONN_FACTURACION_CLIENT_LIB_DIR": "C:/oracle/instantclient_11_2",
        "ORACLE_CONN_CLINICA_USER": "clinica_user",
        "ORACLE_CONN_CLINICA_PASSWORD": "clinica_pass",
        "ORACLE_CONN_CLINICA_HOST": "192.168.1.20",
        "ORACLE_CONN_CLINICA_PORT": "1521",
        "ORACLE_CONN_CLINICA_SID": "ORCL",
        "ORACLE_CONN_CLINICA_CLIENT_LIB_DIR": "C:/oracle/instantclient_11_2"
      }
    }
  }
}
```

Un archivo de ejemplo (`opencode.json.example`) está incluido en el proyecto.

> **Nota de seguridad:** el bloque `environment` de arriba incluye credenciales
> solo con fines de ejemplo. Para datos sensibles, prefiere variables del
> sistema Windows o el archivo `.env` (ver sección 3) y deja `environment` sin
> credenciales.

### Claude Code

Agrega el servidor en `.claude.json` (en la raíz del proyecto o global en `%USERPROFILE%\.claude\`):

```json
{
  "mcpServers": {
    "oracle": {
      "type": "local",
      "command": "C:\\ruta\\oracle-mcp-server\\.venv\\Scripts\\python",
      "args": ["-m", "oracle_mcp.server"],
      "env": {
        "ORACLE_CONNECTIONS": "facturacion",
        "ORACLE_CONN_FACTURACION_USER": "mi_usuario",
        "ORACLE_CONN_FACTURACION_PASSWORD": "mi_password",
        "ORACLE_CONN_FACTURACION_HOST": "192.168.1.10",
        "ORACLE_CONN_FACTURACION_PORT": "1521",
        "ORACLE_CONN_FACTURACION_SID": "ORCL",
        "ORACLE_CONN_FACTURACION_CLIENT_LIB_DIR": "C:\\oracle\\instantclient_11_2"
      }
    }
  }
}
```

### Cursor

En `./cursor/mcp.json` del proyecto:

```json
{
  "mcpServers": {
    "oracle": {
      "type": "local",
      "command": "C:\\ruta\\oracle-mcp-server\\.venv\\Scripts\\python",
      "args": ["-m", "oracle_mcp.server"],
      "env": {
        "ORACLE_CONNECTIONS": "facturacion",
        "ORACLE_CONN_FACTURACION_USER": "mi_usuario",
        "ORACLE_CONN_FACTURACION_PASSWORD": "mi_password",
        "ORACLE_CONN_FACTURACION_HOST": "192.168.1.10",
        "ORACLE_CONN_FACTURACION_PORT": "1521",
        "ORACLE_CONN_FACTURACION_SID": "ORCL",
        "ORACLE_CONN_FACTURACION_CLIENT_LIB_DIR": "C:\\oracle\\instantclient_11_2"
      }
    }
  }
}
```

### Otros clientes MCP

Cualquier cliente que soporte servidores MCP tipo `local`/`stdio` puede usar la misma configuración base:

| Campo | Valor |
|-------|-------|
| command | `C:\ruta\oracle-mcp-server\.venv\Scripts\python` |
| args | `["-m", "oracle_mcp.server"]` |
| env | Tus variables `ORACLE_CONN_*` (o ninguna si usas `.env`) |

**Nota:** Si usas `.env` para las credenciales, el servidor las cargará
automáticamente siempre que el proceso arranque desde la carpeta del proyecto.

### Puntos importantes

- Usa la ruta **absoluta** al Python del `.venv`
- Reinicia/recarga el cliente MCP después de editar la configuración
- Puedes verificar que el servidor responde con el comando de prueba de la sección 4

## 6. Uso de múltiples conexiones

Una vez configuradas las conexiones, puedes usarlas en las tools:

```python
# Usar conexión por defecto (primera de la lista)
list_tables()

# Usar conexión específica
list_tables(connection="clinica")

# Query en conexión específica
run_query("SELECT * FROM pacientes", connection="clinica")

# Ver conexiones disponibles
list_connections()
```

## 7. Notas sobre Oracle 11g y modo thick

- `oracledb.init_oracle_client(lib_dir=...)` se llama **una sola vez**,
  antes de abrir cualquier conexión (lo hace `db.py` automáticamente al
  arrancar el servidor). Usa el `client_lib_dir` de la primera conexión
  que lo tenga definido.
- Si se te olvida configurar `CLIENT_LIB_DIR` y el Instant Client no está
  en el `PATH`/`LD_LIBRARY_PATH`, oracledb lanzará un error indicando que
  no encuentra las librerías cliente.
- 11g casi siempre se conecta por **SID**, no por service_name; por eso el
  DSN se construye con `oracledb.makedsn(host, port, sid=...)` cuando
  defines `SID`.
- Si tu 11g tiene un Oracle Wallet o requiere TNS_ADMIN, puedes exportar
  `TNS_ADMIN` en `environment` dentro de `opencode.json` y ajustar `db.py`
  para usar `dsn` directamente por alias TNS en vez de `makedsn`.

## 8. Estructura del proyecto

```
oracle-mcp-server/
├── pyproject.toml
├── setup.ps1      # Script de instalación automática (Windows)
├── .env.example
├── opencode.json.example
├── README.md
└── src/
    └── oracle_mcp/
        ├── __init__.py
        ├── config.py     # Carga de variables de entorno (multi-conexión)
        ├── db.py          # Init thick mode, multipools, validación SELECT-only
        └── server.py      # Servidor MCP (FastMCP) con tools multi-conexión
```

## 9. Solución de Problemas

| Problema | Causa Común | Solución |
|----------|-------------|----------|
| `Conexión 'xxx' no encontrada` | Nombre no coincide | Verificar que `ORACLE_CONNECTIONS` coincida con las variables |
| `Faltan variables obligatorias` | Variable no definida | Verificar nombre de la variable en Windows o `.env` |
| `Usuario/Password incorrecto` | Credenciales erróneas | Verificar valores con `[Environment]::GetEnvironmentVariable("ORACLE_CONN_FACTURACION_USER", "User")` |
| `Pool no disponible` | Conexión no inicializó | Revisar logs del servidor al iniciar |
| `ORA-12541: TNS:no listener` | Oracle no accessible | Verificar HOST, PORT y que el listener esté activo |
| `ORA-12154: TNS:could not resolve connect identifier` | SID/SERVICE_NAME incorrecto | Verificar ORACLE_SID o ORACLE_SERVICE_NAME |

## 10. Próximos pasos sugeridos

- Agregar paginación real (cursor/offset) en `run_query` si necesitas
  recorrer resultados grandes en varias llamadas.
- Si vas a exponer `execute_statement` en un entorno compartido, considera
  agregar un `ALLOWED_TABLES` o un usuario Oracle con permisos acotados
  (grant solo sobre las tablas necesarias) en vez de confiar únicamente en
  la validación de la tool.
