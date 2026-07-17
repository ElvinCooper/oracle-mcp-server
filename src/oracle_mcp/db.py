"""Capa de acceso a Oracle en modo thick (requerido para Oracle 11g)."""

from __future__ import annotations

import re
import threading

import oracledb

from .config import OracleConfig

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


def init_thick_mode(config: OracleConfig) -> None:
    """Inicializa el Oracle Client en modo thick. Debe llamarse una sola vez,
    antes de abrir cualquier conexion, porque Oracle 11g no soporta thin mode."""
    global _thick_initialized
    with _init_lock:
        if _thick_initialized:
            return
        kwargs = {}
        if config.client_lib_dir:
            kwargs["lib_dir"] = config.client_lib_dir
        oracledb.init_oracle_client(**kwargs)
        _thick_initialized = True


class OracleConnectionManager:
    """Envuelve un pool de conexiones oracledb en modo thick."""

    def __init__(self, config: OracleConfig):
        self._config = config
        self._pool: oracledb.ConnectionPool | None = None

    def start(self) -> None:
        init_thick_mode(self._config)
        self._pool = oracledb.create_pool(
            user=self._config.user,
            password=self._config.password,
            dsn=self._config.dsn,
            min=self._config.pool_min,
            max=self._config.pool_max,
            increment=1,
        )

    def stop(self) -> None:
        if self._pool is not None:
            self._pool.close(force=True)
            self._pool = None

    @property
    def pool(self) -> oracledb.ConnectionPool:
        if self._pool is None:
            raise RuntimeError("El pool de conexiones no ha sido inicializado.")
        return self._pool


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
        result.append({col: _serialize(val) for col, val in zip(columns, row)})
    return result


def _serialize(value):
    # LOBs y tipos no serializables directamente a JSON se convierten a str/bytes-safe.
    if isinstance(value, oracledb.LOB):
        try:
            return value.read()
        except Exception:
            return "<LOB>"
    return value
