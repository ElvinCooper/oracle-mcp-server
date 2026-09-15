"""Capa de acceso a Oracle en modo thick (requerido para Oracle 11g)."""

from __future__ import annotations

import logging
import re
import threading

import oracledb

from .config import OracleConfig, OracleConnectionConfig

logger = logging.getLogger("oracle_mcp")

_init_lock = threading.Lock()
_thick_initialized = False

# Palabras clave que consideramos de escritura/DDL. Cualquier sentencia que
# empiece con una de estas requiere la tool execute_statement (y ALLOW_WRITE=true).
_WRITE_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "MERGE", "CREATE", "ALTER", "DROP",
    "TRUNCATE", "GRANT", "REVOKE", "REPLACE",
)


class QueryValidationError(ValueError):
    """Se lanza cuando una consulta no cumple las reglas de seguridad del MCP."""


def init_thick_mode(connections: list[OracleConnectionConfig]) -> None:
    """Inicializa el Oracle Client en modo thick. Debe llamarse una sola vez,
    antes de abrir cualquier conexion, porque Oracle 11g no soporta thin mode.

    Usa el client_lib_dir de la primera conexion que lo tenga definido.
    """
    global _thick_initialized
    with _init_lock:
        if _thick_initialized:
            return

        # Buscar la primera conexion con client_lib_dir definido
        lib_dir = None
        for conn in connections:
            if conn.client_lib_dir:
                lib_dir = conn.client_lib_dir
                break

        kwargs = {}
        if lib_dir:
            kwargs["lib_dir"] = lib_dir
        oracledb.init_oracle_client(**kwargs)
        _thick_initialized = True
        logger.info("Oracle Client inicializado en modo thick")


class OracleConnectionManager:
    """Envuelve multipools de conexiones oracledb en modo thick."""

    def __init__(self, config: OracleConfig):
        self._config = config
        self._pools: dict[str, oracledb.ConnectionPool] = {}

    def start(self) -> None:
        """Inicializa pools para todas las conexiones configuradas."""
        init_thick_mode(self._config.connections)

        for conn_config in self._config.connections:
            try:
                pool = oracledb.create_pool(
                    user=conn_config.user,
                    password=conn_config.password,
                    dsn=conn_config.dsn,
                    min=conn_config.pool_min,
                    max=conn_config.pool_max,
                    increment=1,
                )
                self._pools[conn_config.name] = pool
            except Exception as e:
                logger.error("Error iniciando pool '%s': %s", conn_config.name, e)

        logger.info("Pools Oracle listos: %d", len(self._pools))

    def stop(self) -> None:
        """Cierra todos los pools."""
        count = len(self._pools)
        for name, pool in self._pools.items():
            try:
                pool.close(force=True)
            except Exception as e:
                logger.error("Error cerrando pool '%s': %s", name, e)
        self._pools.clear()
        logger.info("Pools Oracle cerrados: %d", count)

    def get_pool(self, connection_name: str | None = None) -> oracledb.ConnectionPool:
        """Retorna el pool para la conexion especificada.

        Si connection_name es None, usa la conexion por defecto.
        """
        if connection_name is None:
            connection_name = self._config.default_connection.name

        if connection_name not in self._pools:
            available = list(self._pools.keys())
            raise RuntimeError(
                f"Pool '{connection_name}' no disponible. "
                f"Pools activos: {available}"
            )

        return self._pools[connection_name]


def _first_keyword(sql: str) -> str:
    stripped = re.sub(r"^\s*(--.*\n|/\*.*?\*/\s*)*", "", sql, flags=re.DOTALL).strip()
    match = re.match(r"([A-Za-z]+)", stripped)
    return match.group(1).upper() if match else ""


def assert_select_only(sql: str) -> None:
    """Verifica que la sentencia sea unicamente de lectura (SELECT / WITH)."""
    keyword = _first_keyword(sql)
    if keyword not in ("SELECT", "WITH"):
        raise QueryValidationError(
            f"Solo se permiten sentencias SELECT en esta tool. Se detecto: '{keyword or sql[:30]}'. "
            "Si necesitas escribir datos usa la tool execute_statement (requiere ORACLE_ALLOW_WRITE=true)."
        )
    if ";" in sql.strip().rstrip(";"):
        raise QueryValidationError(
            "No se permiten multiples sentencias separadas por ';' en una sola llamada."
        )


def assert_write_allowed(sql: str, allow_write: bool) -> None:
    if not allow_write:
        raise QueryValidationError(
            "La escritura esta deshabilitada. Define ORACLE_ALLOW_WRITE=true en el .env para habilitarla."
        )
    keyword = _first_keyword(sql)
    if keyword not in _WRITE_KEYWORDS + ("SELECT", "WITH"):
        raise QueryValidationError(f"Sentencia no reconocida/soportada: '{keyword}'.")


def rows_to_dicts(cursor: oracledb.Cursor, rows: list) -> list[dict]:
    columns = [col[0] for col in cursor.description]
    result = []
    for row in rows:
        result.append({col: _serialize(val) for col, val in zip(columns, row, strict=False)})
    return result


def _serialize(value):
    # LOBs y tipos no serializables directamente a JSON se convierten a str/bytes-safe.
    if isinstance(value, oracledb.LOB):
        try:
            return value.read()
        except Exception:
            return "<LOB>"
    return value
