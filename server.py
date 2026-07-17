"""Servidor MCP para Oracle 11g (thick mode) usando el SDK oficial de Python.

Uso:
    python -m oracle_mcp.server

Se comunica por stdio, tal como lo espera opencode / Claude Code / cualquier
cliente MCP que lance procesos locales ("type": "local"/"stdio").
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass

from mcp.server.fastmcp import Context, FastMCP

from .config import OracleConfig, load_config
from .db import (
    OracleConnectionManager,
    QueryValidationError,
    assert_select_only,
    assert_write_allowed,
    rows_to_dicts,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("oracle_mcp")


@dataclass
class AppContext:
    config: OracleConfig
    conn_mgr: OracleConnectionManager


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    config = load_config()
    conn_mgr = OracleConnectionManager(config)
    logger.info("Inicializando Oracle Client en modo thick y pool de conexiones...")
    conn_mgr.start()
    logger.info("Pool de conexiones Oracle listo (min=%s, max=%s).", config.pool_min, config.pool_max)
    try:
        yield AppContext(config=config, conn_mgr=conn_mgr)
    finally:
        conn_mgr.stop()
        logger.info("Pool de conexiones Oracle cerrado.")


mcp = FastMCP("oracle-11g", lifespan=app_lifespan)


def _ctx_app(ctx) -> AppContext:
    return ctx.request_context.lifespan_context


@mcp.tool()
def list_tables(ctx: Context, schema: str | None = None) -> list[dict]:
    """Lista las tablas disponibles en un schema (por defecto el usuario actual).

    Args:
        schema: Nombre del schema/owner en mayusculas (ej. 'VENTAS'). Si se omite,
            se listan las tablas del usuario con el que se conecta el MCP.
    """
    app = _ctx_app(ctx)
    pool = app.conn_mgr.pool
    with pool.acquire() as conn, conn.cursor() as cur:
        if schema:
            cur.execute(
                "SELECT table_name FROM all_tables WHERE owner = :owner ORDER BY table_name",
                owner=schema.upper(),
            )
        else:
            cur.execute("SELECT table_name FROM user_tables ORDER BY table_name")
        return rows_to_dicts(cur, cur.fetchall())


@mcp.tool()
def describe_table(ctx: Context, table_name: str, schema: str | None = None) -> list[dict]:
    """Describe las columnas de una tabla: nombre, tipo, nulabilidad y longitud.

    Args:
        table_name: Nombre de la tabla (sin comillas, se normaliza a mayusculas).
        schema: Owner de la tabla si es distinto al usuario actual.
    """
    app = _ctx_app(ctx)
    pool = app.conn_mgr.pool
    with pool.acquire() as conn, conn.cursor() as cur:
        if schema:
            cur.execute(
                """
                SELECT column_name, data_type, nullable, data_length, data_precision, data_scale
                FROM all_tab_columns
                WHERE owner = :owner AND table_name = :tname
                ORDER BY column_id
                """,
                owner=schema.upper(),
                tname=table_name.upper(),
            )
        else:
            cur.execute(
                """
                SELECT column_name, data_type, nullable, data_length, data_precision, data_scale
                FROM user_tab_columns
                WHERE table_name = :tname
                ORDER BY column_id
                """,
                tname=table_name.upper(),
            )
        return rows_to_dicts(cur, cur.fetchall())


@mcp.tool()
def run_query(ctx: Context, sql: str, max_rows: int | None = None) -> dict:
    """Ejecuta una consulta SELECT de solo lectura contra Oracle y devuelve las filas.

    Solo se permiten sentencias SELECT/WITH (sin punto y coma multiple). El numero
    de filas devuelto se limita para no saturar el contexto del modelo.

    Args:
        sql: Sentencia SQL de tipo SELECT.
        max_rows: Limite opcional de filas (por defecto usa ORACLE_MAX_ROWS).
    """
    app = _ctx_app(ctx)
    try:
        assert_select_only(sql)
    except QueryValidationError as exc:
        return {"error": str(exc)}

    limit = max_rows or app.config.max_rows
    pool = app.conn_mgr.pool
    with pool.acquire() as conn, conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchmany(limit)
        truncated = cur.fetchone() is not None
        return {
            "rows": rows_to_dicts(cur, rows),
            "row_count": len(rows),
            "truncated": truncated,
            "limit_applied": limit,
        }


@mcp.tool()
def execute_statement(ctx: Context, sql: str, confirm: bool = False) -> dict:
    """Ejecuta INSERT/UPDATE/DELETE/DDL. Deshabilitado por defecto.

    Requiere ORACLE_ALLOW_WRITE=true en el entorno del servidor Y confirm=True
    en la llamada, como doble seguro contra escrituras accidentales.

    Args:
        sql: Sentencia SQL de escritura (INSERT/UPDATE/DELETE/CREATE/ALTER/DROP...).
        confirm: Debe ser True explicitamente para ejecutar la sentencia.
    """
    app = _ctx_app(ctx)
    try:
        assert_write_allowed(sql, app.config.allow_write)
    except QueryValidationError as exc:
        return {"error": str(exc)}

    if not confirm:
        return {
            "error": "Confirmacion requerida: vuelve a llamar la tool con confirm=true "
                     "para ejecutar esta sentencia de escritura.",
            "sql_preview": sql[:200],
        }

    pool = app.conn_mgr.pool
    with pool.acquire() as conn, conn.cursor() as cur:
        cur.execute(sql)
        conn.commit()
        return {"rows_affected": cur.rowcount, "status": "ok"}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
