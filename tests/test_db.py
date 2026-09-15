"""Pruebas de la capa de datos sin conexion a Oracle ni Instant Client."""

import pytest

from oracle_mcp.config import OracleConfig
from oracle_mcp.db import (
    OracleConnectionManager,
    QueryValidationError,
    _WRITE_KEYWORDS,
    _first_keyword,
    _serialize,
    assert_select_only,
    assert_write_allowed,
    init_thick_mode,
    rows_to_dicts,
)
from tests.helpers import make_connection


@pytest.fixture
def thick_calls(monkeypatch):
    """Resetea el estado del modo thick y captura init_oracle_client."""
    calls = []

    def fake_init(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("oracle_mcp.db._thick_initialized", False)
    monkeypatch.setattr("oracledb.init_oracle_client", fake_init)
    return calls


# ---------------------------------------------------------------------------
# init_thick_mode
# ---------------------------------------------------------------------------


def test_init_thick_una_sola_vez_con_lib_dir(thick_calls):
    conns = [
        make_connection(name="a", client_lib_dir=r"C:\instantclient"),
        make_connection(name="b"),
    ]
    init_thick_mode(conns)
    init_thick_mode(conns)
    assert thick_calls == [{"lib_dir": r"C:\instantclient"}]


def test_init_thick_sin_lib_dir(thick_calls):
    init_thick_mode([make_connection(name="a")])
    assert thick_calls == [{}]


def test_init_thick_usa_primer_lib_dir_definido(thick_calls):
    conns = [
        make_connection(name="a"),
        make_connection(name="b", client_lib_dir=r"D:\cli"),
    ]
    init_thick_mode(conns)
    assert thick_calls == [{"lib_dir": r"D:\cli"}]


# ---------------------------------------------------------------------------
# Validacion de sentencias
# ---------------------------------------------------------------------------


def test_query_validation_error_es_valueerror():
    assert issubclass(QueryValidationError, ValueError)


def test_write_keywords_principales():
    assert {"INSERT", "UPDATE", "DELETE", "MERGE", "CREATE", "ALTER", "DROP"} <= set(
        _WRITE_KEYWORDS
    )


@pytest.mark.parametrize(
    "sql,esperado",
    [
        ("SELECT * FROM t", "SELECT"),
        ("  select id from t", "SELECT"),
        ("SELECT\n1", "SELECT"),
        ("WITH x AS (SELECT 1) SELECT * FROM x", "WITH"),
        ("-- comentario\nSELECT 1", "SELECT"),
        ("/* bloque */ SELECT 1", "SELECT"),
        ("  INSERT INTO t VALUES (1)", "INSERT"),
    ],
)
def test_first_keyword(sql, esperado):
    assert _first_keyword(sql) == esperado


def test_first_keyword_vacio():
    assert _first_keyword("") == ""
    assert _first_keyword("   ;  ") == ""


@pytest.mark.parametrize("sql", ["SELECT 1", "select 1", "WITH t AS (SELECT 1) SELECT * FROM t"])
def test_select_only_acepta_lectura(sql):
    assert_select_only(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO t VALUES (1)",
        "UPDATE t SET a = 1",
        "DELETE FROM t",
        "CREATE TABLE t (a NUMBER)",
        "ALTER TABLE t ADD c NUMBER",
        "DROP TABLE t",
        "TRUNCATE TABLE t",
        "MERGE INTO t USING s ON (1 = 1) WHEN MATCHED THEN UPDATE SET a = 1",
        "GRANT SELECT ON t TO u",
        "FOO 1",
    ],
)
def test_select_only_rechaza_escritura_o_desconocida(sql):
    with pytest.raises(QueryValidationError):
        assert_select_only(sql)


def test_select_only_rechaza_multiples_sentencias():
    with pytest.raises(QueryValidationError, match="multiples sentencias"):
        assert_select_only("SELECT 1; SELECT 2")


def test_select_only_permite_punto_y_coma_final():
    assert_select_only("SELECT 1;")


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
def test_write_allowed_deshabilitado_rechaza_toda_escritura(sql):
    with pytest.raises(QueryValidationError, match="ORACLE_ALLOW_WRITE"):
        assert_write_allowed(sql, allow_write=False)


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
        "REPLACE INTO t VALUES (1)",
        "SELECT 1",
        "WITH x AS (SELECT 1) SELECT * FROM x",
    ],
)
def test_write_allowed_acepta_reconocidas(sql):
    assert_write_allowed(sql, allow_write=True)


@pytest.mark.parametrize("sql", ["FOO 1", "PURGE TABLE t", "EXPLAIN SELECT 1"])
def test_write_allowed_rechaza_desconocidas(sql):
    with pytest.raises(QueryValidationError):
        assert_write_allowed(sql, allow_write=True)


# ---------------------------------------------------------------------------
# Serializacion de filas / LOBs
# ---------------------------------------------------------------------------


class FakeCursor:
    def __init__(self, description=None):
        self._description = description or [("COL_A",), ("COL_B",)]

    @property
    def description(self):
        return self._description


class _FakeLOB:
    """Sustituto ligero de oracledb.LOB (evita el deallocator del real)."""

    def __init__(self, value=None, broken=False):
        self._value = value
        self._broken = broken

    def read(self):
        if self._broken:
            raise RuntimeError("LOB no disponible")
        return self._value


@pytest.fixture
def fake_lob(monkeypatch):
    """Reemplaza oracledb.LOB por _FakeLOB dentro de oracle_mcp.db."""
    monkeypatch.setattr("oracledb.LOB", _FakeLOB)
    return _FakeLOB


def test_rows_to_dicts_con_lobs(fake_lob):
    cursor = FakeCursor()
    rows = [(1, fake_lob(b"datos")), (2, None)]
    assert rows_to_dicts(cursor, rows) == [
        {"COL_A": 1, "COL_B": b"datos"},
        {"COL_A": 2, "COL_B": None},
    ]


def test_serialize_lob_roto_devuelve_placeholder(fake_lob):
    assert _serialize(fake_lob(broken=True)) == "<LOB>"


def test_serialize_pasa_valores_normales():
    assert _serialize(3.14) == 3.14
    assert _serialize("texto") == "texto"
    assert _serialize(None) is None


# ---------------------------------------------------------------------------
# OracleConnectionManager
# ---------------------------------------------------------------------------


def _manager(config: OracleConfig) -> OracleConnectionManager:
    mgr = OracleConnectionManager(config)
    fake = object()
    mgr._pools = {c.name: fake for c in config.connections}
    return mgr


def test_manager_get_pool_por_defecto_y_nombre():
    config = OracleConfig(connections=[make_connection(name="a"), make_connection(name="b")])
    mgr = _manager(config)
    assert mgr.get_pool() is mgr._pools["a"]
    assert mgr.get_pool("b") is mgr._pools["b"]


def test_manager_get_pool_inexistente_lanza():
    config = OracleConfig(connections=[make_connection(name="a")])
    mgr = _manager(config)
    with pytest.raises(RuntimeError, match="no disponible"):
        mgr.get_pool("zzz")


def test_manager_start_crea_pools(monkeypatch):
    past_pools = []

    def fake_create_pool(**kwargs):
        pool = object()
        past_pools.append(pool)
        return pool

    monkeypatch.setattr("oracledb.create_pool", fake_create_pool)
    monkeypatch.setattr("oracle_mcp.db._thick_initialized", True)

    config = OracleConfig(connections=[make_connection(name="a"), make_connection(name="b")])
    mgr = OracleConnectionManager(config)
    mgr.start()
    assert len(mgr._pools) == 2
    assert mgr._pools["a"] is past_pools[0]
    assert mgr._pools["b"] is past_pools[1]