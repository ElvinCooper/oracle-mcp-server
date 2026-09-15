"""Pruebas de las tools del servidor MCP con pools/contexto ficticios.

No conecta a Oracle real: simula cursor/pool/manejador para ejercitar la
logica de cada tool (validacion, limites, confirmacion, conexion por defecto).
"""

import pytest

import oracle_mcp.server as server
from oracle_mcp.config import OracleConfig
from oracle_mcp.db import OracleConnectionManager
from tests.helpers import make_connection


class FakeCursor:
    def __init__(self, rows=(), description=(), rowcount=0, extra=None):
        self._rows = list(rows)
        self._description = description
        self._rowcount = rowcount
        self._extra = extra
        self.executed = None

    @property
    def description(self):
        return self._description

    @property
    def rowcount(self):
        return self._rowcount

    def execute(self, sql, **params):
        self.executed = (sql, params)

    def fetchall(self):
        return self._rows

    def fetchmany(self, n):
        return self._rows[:n]

    def fetchone(self):
        return self._extra


class FakeCursorManager:
    """FakeCursor con protocolo context manager para ``conn.cursor()``."""

    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self._cursor

    def __exit__(self, *exc):
        return False


class FakeConn:
    def __init__(self, cursor):
        self._cursor_manager = FakeCursorManager(cursor)
        self.commits = 0

    def cursor(self):
        return self._cursor_manager

    def commit(self):
        self.commits += 1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakePool:
    def __init__(self, cursor):
        self._cursor = cursor
        self.acquisitions = 0

    def acquire(self):
        self.acquisitions += 1
        return FakeConn(self._cursor)


class FakeCtx:
    """Minimo ctx que expone request_context.lifespan_context (= AppContext)."""

    def __init__(self, app):
        self.app = app

    class _Lifespan:
        def __init__(self, app):
            self.lifespan_context = app

    @property
    def request_context(self):
        return self._Lifespan(self.app)


def _make_app(pools=None, connections=None):
    conns = connections or [make_connection(name="a")]
    config = OracleConfig(connections=conns)
    mgr = OracleConnectionManager(config)
    mgr._pools = pools or {c.name: FakePool(FakeCursor()) for c in conns}
    return server.AppContext(config=config, conn_mgr=mgr)


def _ctx(app):
    return FakeCtx(app)


def _cursor(rows=(), description=(), rowcount=0, extra=None):
    return FakeCursor(rows=rows, description=description, rowcount=rowcount, extra=extra)


# ---------------------------------------------------------------------------
# list_connections
# ---------------------------------------------------------------------------


def test_list_connections():
    conns = [
        make_connection(name="a"),
        make_connection(name="b", port=1522, sid=None, service_name="XDB"),
    ]
    app = _make_app(connections=conns)
    result = server.list_connections(_ctx(app))

    assert result[0] == {
        "name": "a",
        "host": "localhost",
        "port": 1521,
        "sid": "ORCL",
        "service_name": None,
        "user": "scott",
        "is_default": True,
    }
    assert result[1]["is_default"] is False
    assert result[1]["service_name"] == "XDB"


# ---------------------------------------------------------------------------
# list_tables
# ---------------------------------------------------------------------------


def test_list_tables_sin_schema():
    cursor = _cursor(rows=[("EMP",), ("DEPT",)], description=[("TABLE_NAME",)])
    app = _make_app(pools={"a": FakePool(cursor)})
    result = server.list_tables(_ctx(app), connection="a")

    sql, params = cursor.executed
    assert sql == "SELECT table_name FROM user_tables ORDER BY table_name"
    assert params == {}
    assert result == [{"TABLE_NAME": "EMP"}, {"TABLE_NAME": "DEPT"}]


def test_list_tables_con_schema():
    cursor = _cursor(rows=[("T1",)], description=[("TABLE_NAME",)])
    app = _make_app(pools={"a": FakePool(cursor)})
    server.list_tables(_ctx(app), schema="ventas", connection="a")

    sql, params = cursor.executed
    assert "FROM all_tables" in sql
    assert "owner = :owner" in sql
    assert params == {"owner": "VENTAS"}


# ---------------------------------------------------------------------------
# describe_table
# ---------------------------------------------------------------------------


def test_describe_table_sin_schema():
    description = [
        ("COLUMN_NAME",),
        ("DATA_TYPE",),
        ("NULLABLE",),
        ("DATA_LENGTH",),
        ("DATA_PRECISION",),
        ("DATA_SCALE",),
    ]
    cursor = _cursor(rows=[("ID", "NUMBER", "N", 22, None, None)], description=description)
    app = _make_app(pools={"a": FakePool(cursor)})
    result = server.describe_table(_ctx(app), table_name="emp", connection="a")

    sql, params = cursor.executed
    assert "FROM user_tab_columns" in sql
    assert params == {"tname": "EMP"}
    assert result[0] == {
        "COLUMN_NAME": "ID",
        "DATA_TYPE": "NUMBER",
        "NULLABLE": "N",
        "DATA_LENGTH": 22,
        "DATA_PRECISION": None,
        "DATA_SCALE": None,
    }


def test_describe_table_con_schema():
    description = [("COLUMN_NAME",)]
    cursor = _cursor(rows=[("ID",)], description=description)
    app = _make_app(pools={"a": FakePool(cursor)})
    server.describe_table(_ctx(app), table_name="emp", schema="ventas", connection="a")

    sql, params = cursor.executed
    assert "FROM all_tab_columns" in sql
    assert params == {"owner": "VENTAS", "tname": "EMP"}


# ---------------------------------------------------------------------------
# run_query
# ---------------------------------------------------------------------------


def test_run_query_devuelve_filas():
    cursor = _cursor(rows=[(1,), (2,)], description=[("N",)])
    app = _make_app(pools={"a": FakePool(cursor)})
    result = server.run_query(_ctx(app), sql="SELECT 1 FROM dual", connection="a")

    assert cursor.executed == ("SELECT 1 FROM dual", {})
    assert result["rows"] == [{"N": 1}, {"N": 2}]
    assert result["row_count"] == 2
    assert result["truncated"] is False
    assert result["limit_applied"] == 200
    assert result["connection"] == "a"


def test_run_query_usa_conexion_por_defecto():
    cursor = _cursor(rows=[(1,)], description=[("N",)])
    app = _make_app(pools={"a": FakePool(cursor)})
    result = server.run_query(_ctx(app), sql="SELECT 1 FROM dual")
    assert result["connection"] == "a"


def test_run_query_trunca_con_max_rows():
    cursor = _cursor(rows=[(1,), (2,), (3,)], description=[("N",)], extra=(4,))
    app = _make_app(pools={"a": FakePool(cursor)})
    result = server.run_query(
        _ctx(app), sql="SELECT 1 FROM dual", connection="a", max_rows=2
    )
    assert result["row_count"] == 2
    assert result["truncated"] is True
    assert result["limit_applied"] == 2


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO t VALUES (1)",
        "UPDATE t SET a = 1",
        "DELETE FROM t",
        "MERGE INTO t USING s ON (1 = 1) WHEN MATCHED THEN UPDATE SET a = 1",
        "CREATE TABLE t (a NUMBER)",
        "ALTER TABLE t ADD c NUMBER",
        "DROP TABLE t",
        "TRUNCATE TABLE t",
        "GRANT SELECT ON t TO u",
        "REVOKE SELECT ON t FROM u",
        "REPLACE INTO t VALUES (1)",
    ],
)
def test_run_query_rechaza_escrituras_sin_usar_pool(sql):
    pool = FakePool(_cursor())
    app = _make_app(pools={"a": pool})
    result = server.run_query(_ctx(app), sql=sql, connection="a")
    assert "error" in result
    assert "SELECT" in result["error"]
    assert pool.acquisitions == 0


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1 FROM dual",
        "WITH x AS (SELECT 1 FROM dual) SELECT * FROM x",
    ],
)
def test_run_query_acepta_select_y_with(sql):
    cursor = _cursor(rows=[(1,)], description=[("N",)])
    app = _make_app(pools={"a": FakePool(cursor)})
    result = server.run_query(_ctx(app), sql=sql, connection="a")
    assert cursor.executed == (sql, {})
    assert result["rows"] == [{"N": 1}]
    assert result["truncated"] is False


def test_run_query_rechaza_multiples_sentencias():
    pool = FakePool(_cursor())
    app = _make_app(pools={"a": pool})
    result = server.run_query(
        _ctx(app),
        sql="SELECT 1 FROM dual; SELECT 2 FROM dual",
        connection="a",
    )
    assert "multiples sentencias" in result["error"]
    assert pool.acquisitions == 0


def test_run_query_max_rows_cero_usa_default_de_config():
    cursor = _cursor(rows=[(1,)], description=[("N",)])
    app = _make_app(pools={"a": FakePool(cursor)})
    result = server.run_query(_ctx(app), sql="SELECT 1 FROM dual", connection="a", max_rows=0)
    assert result["limit_applied"] == 200


def test_run_query_connection_desconocida_lanza():
    app = _make_app()
    with pytest.raises(ValueError, match="no encontrada"):
        server.run_query(_ctx(app), sql="SELECT 1", connection="inexistente")


# ---------------------------------------------------------------------------
# execute_statement
# ---------------------------------------------------------------------------


def test_execute_statement_escritura_deshabilitada():
    conns = [make_connection(name="a", allow_write=False)]
    pool = FakePool(_cursor())
    app = _make_app(pools={"a": pool}, connections=conns)
    result = server.execute_statement(
        _ctx(app), sql="INSERT INTO t VALUES (1)", connection="a", confirm=True
    )
    assert "ORACLE_ALLOW_WRITE" in result["error"]
    assert pool.acquisitions == 0


def test_execute_statement_requiere_confirm():
    conns = [make_connection(name="a", allow_write=True)]
    app = _make_app(pools={"a": FakePool(_cursor())}, connections=conns)
    result = server.execute_statement(
        _ctx(app), sql="INSERT INTO t VALUES (1)", connection="a", confirm=False
    )
    assert "confirm=true" in result["error"]
    assert result["sql_preview"] == "INSERT INTO t VALUES (1)"
    assert result["connection"] == "a"


def test_execute_statement_ok():
    conns = [make_connection(name="a", allow_write=True)]
    cursor = _cursor(rowcount=3)
    app = _make_app(pools={"a": FakePool(cursor)}, connections=conns)
    result = server.execute_statement(
        _ctx(app), sql="INSERT INTO t VALUES (1)", connection="a", confirm=True
    )
    assert result == {"rows_affected": 3, "status": "ok", "connection": "a"}


def test_execute_statement_permite_select_con_write():
    conns = [make_connection(name="a", allow_write=True)]
    app = _make_app(pools={"a": FakePool(_cursor())}, connections=conns)
    result = server.execute_statement(
        _ctx(app), sql="SELECT 1 FROM dual", connection="a", confirm=True
    )
    assert result["status"] == "ok"


def test_execute_statement_sentencia_no_soportada():
    conns = [make_connection(name="a", allow_write=True)]
    app = _make_app(pools={"a": FakePool(_cursor())}, connections=conns)
    result = server.execute_statement(
        _ctx(app), sql="PURGE TABLE t", connection="a", confirm=True
    )
    assert "no reconocida" in result["error"]


def test_execute_statement_config_por_conexion():
    conns = [
        make_connection(name="rw", allow_write=True),
        make_connection(name="ro", allow_write=False),
    ]
    ro_pool = FakePool(_cursor())
    rw_pool = FakePool(_cursor(rowcount=1))
    app = _make_app(pools={"rw": rw_pool, "ro": ro_pool}, connections=conns)
    sql = "INSERT INTO t VALUES (1)"

    result_ro = server.execute_statement(_ctx(app), sql=sql, connection="ro", confirm=True)
    assert "ORACLE_ALLOW_WRITE" in result_ro["error"]
    assert ro_pool.acquisitions == 0

    result_rw = server.execute_statement(_ctx(app), sql=sql, connection="rw", confirm=True)
    assert result_rw["status"] == "ok"
    assert rw_pool.acquisitions == 1
