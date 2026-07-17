# oracle-mcp-server

Servidor MCP (Model Context Protocol) en Python para conectar a **Oracle 11g**
usando `python-oracledb` en **modo thick** (obligatorio en 11g, ya que el modo
thin del driver solo soporta Oracle 12.1+). Pensado para usarse desde
[opencode](https://opencode.ai) u otro cliente MCP compatible con servidores
locales (stdio).

## Tools expuestas

| Tool | Descripción |
|---|---|
| `list_tables` | Lista tablas de un schema (o del usuario actual) |
| `describe_table` | Devuelve columnas, tipo de dato, nulabilidad, longitud |
| `run_query` | Ejecuta un `SELECT` de solo lectura, con límite de filas |
| `execute_statement` | Ejecuta `INSERT/UPDATE/DELETE/DDL`, **deshabilitado por defecto** |

### Seguridad por diseño

- Por defecto **solo lectura**: `run_query` valida que la sentencia empiece
  con `SELECT`/`WITH` y rechaza múltiples sentencias separadas por `;`.
- `execute_statement` está bloqueada salvo que definas
  `ORACLE_ALLOW_WRITE=true` en el entorno **y** pases `confirm=true` en la
  llamada (doble seguro).
- Las credenciales viven en variables de entorno, nunca hardcodeadas.

## 1. Requisitos previos

- Python 3.10+
- Oracle Instant Client ya instalado (dijiste que ya lo tienes disponible).
  Necesitas la ruta del directorio con `libclntsh.so` (Linux/Mac) o
  `oci.dll` (Windows), por ejemplo `/opt/oracle/instantclient_11_2`.
- Acceso de red al listener de Oracle (host:puerto) y un SID o service_name.

## 2. Instalación

```bash
cd oracle-mcp-server
python3 -m venv .venv
source .venv/bin/activate      # En Windows: .venv\Scripts\activate
pip install -e .
```

## 3. Configuración

Copia `.env.example` a `.env` y completa tus datos:

```bash
cp .env.example .env
```

Variables clave:

- `ORACLE_USER`, `ORACLE_PASSWORD`, `ORACLE_HOST`, `ORACLE_PORT`
- `ORACLE_SID` **o** `ORACLE_SERVICE_NAME` (11g normalmente usa SID)
- `ORACLE_CLIENT_LIB_DIR`: ruta al Instant Client (thick mode)
- `ORACLE_ALLOW_WRITE`: `false` por defecto
- `ORACLE_MAX_ROWS`: límite de filas por consulta (protege el contexto del LLM)

## 4. Probarlo de forma independiente

Puedes levantar el servidor manualmente para verificar que conecta:

```bash
source .venv/bin/activate
python -m oracle_mcp.server
```

Si ves en el log `Pool de conexiones Oracle listo`, la conexión en thick
mode funcionó. El proceso queda esperando mensajes MCP por stdio (Ctrl+C
para salir). Para probarlo como un cliente MCP real, puedes usar el
inspector oficial:

```bash
npx @modelcontextprotocol/inspector python -m oracle_mcp.server
```

## 5. Integración con opencode

opencode define servidores MCP en el bloque `mcp` de `opencode.json`
(global en `~/.config/opencode/opencode.json` o local en la raíz del
proyecto). Usa `"type": "local"` con un `command` (array) para servidores
stdio, y `environment` para pasar las variables sin escribirlas en el JSON
si prefieres exportarlas antes.

Toma como base `opencode.json.example` (incluido en este repo):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "oracle-11g": {
      "type": "local",
      "command": [
        "/ruta/al/proyecto/oracle-mcp-server/.venv/bin/python",
        "-m",
        "oracle_mcp.server"
      ],
      "enabled": true,
      "environment": {
        "ORACLE_USER": "mi_usuario",
        "ORACLE_PASSWORD": "mi_password",
        "ORACLE_HOST": "192.168.1.10",
        "ORACLE_PORT": "1521",
        "ORACLE_SID": "ORCL",
        "ORACLE_CLIENT_LIB_DIR": "/opt/oracle/instantclient_11_2",
        "ORACLE_ALLOW_WRITE": "false",
        "ORACLE_MAX_ROWS": "200"
      }
    }
  }
}
```

Puntos importantes:

- Usa la ruta **absoluta** al Python del `.venv` que creaste en el paso 2
  (así opencode no depende de que el venv esté activado).
- Si prefieres no meter credenciales en `opencode.json`, deja `environment`
  vacío y exporta las variables (o usa el `.env`) antes de lanzar opencode;
  `python-dotenv` las cargará automáticamente si el proceso arranca desde
  la carpeta del proyecto.
- Reinicia/recarga opencode después de editar la config para que detecte
  el nuevo servidor. Puedes verificar con `opencode mcp list`.

## 6. Notas sobre Oracle 11g y modo thick

- `oracledb.init_oracle_client(lib_dir=...)` se llama **una sola vez**,
  antes de abrir cualquier conexión (lo hace `db.py` automáticamente al
  arrancar el servidor). Si se te olvida configurar `ORACLE_CLIENT_LIB_DIR`
  y el Instant Client no está en el `PATH`/`LD_LIBRARY_PATH`, oracledb
  lanzará un error indicando que no encuentra las librerías cliente.
- 11g casi siempre se conecta por **SID**, no por service_name; por eso el
  DSN se construye con `oracledb.makedsn(host, port, sid=...)` cuando
  defines `ORACLE_SID`.
- Si tu 11g tiene un Oracle Wallet o requiere TNS_ADMIN, puedes exportar
  `TNS_ADMIN` en `environment` dentro de `opencode.json` y ajustar `db.py`
  para usar `dsn` directamente por alias TNS en vez de `makedsn`.

## 7. Estructura del proyecto

```
oracle-mcp-server/
├── pyproject.toml
├── .env.example
├── opencode.json.example
├── README.md
└── src/
    └── oracle_mcp/
        ├── __init__.py
        ├── config.py     # Carga de variables de entorno
        ├── db.py          # Init thick mode, pool, validación SELECT-only
        └── server.py      # Servidor MCP (FastMCP) con las 4 tools
```

## 8. Próximos pasos sugeridos

- Agregar una tool `list_schemas` (`SELECT username FROM all_users`) si
  trabajas con varios schemas.
- Agregar paginación real (cursor/offset) en `run_query` si necesitas
  recorrer resultados grandes en varias llamadas.
- Si vas a exponer `execute_statement` en un entorno compartido, considera
  agregar un `ALLOWED_TABLES` o un usuario Oracle con permisos acotados
  (grant solo sobre las tablas necesarias) en vez de confiar únicamente en
  la validación de la tool.
