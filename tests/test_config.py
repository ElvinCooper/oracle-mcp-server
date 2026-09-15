"""Pruebas de carga y validacion de configuracion desde variables de entorno."""

import pytest

from oracle_mcp.config import OracleConfig, load_config
from tests.helpers import make_connection


def _set_legacy(monkeypatch, **kwargs):
    """Establece el entorno legacy ORACLE_* para una conexion "default" completa."""
    values = {
        "ORACLE_USER": "scott",
        "ORACLE_PASSWORD": "tiger",
        "ORACLE_HOST": "localhost",
        "ORACLE_SID": "ORCL",
    }
    values.update(kwargs)
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def _set_multi(monkeypatch, names, **kwargs):
    """Establece conexiones multi con credenciales por defecto (sobrescribibles)."""
    monkeypatch.setenv("ORACLE_CONNECTIONS", ",".join(names))
    base = {
        "USER": "scott",
        "PASSWORD": "tiger",
        "HOST": "localhost",
        "SID": "ORCL",
    }
    base.update(kwargs)
    for name in names:
        prefix = f"ORACLE_CONN_{name.upper()}"
        for key, value in base.items():
            monkeypatch.setenv(f"{prefix}_{key}", value)


# ---------------------------------------------------------------------------
# load_config / formato
# ---------------------------------------------------------------------------


def test_sin_configuracion_lanza_error(monkeypatch):
    with pytest.raises(RuntimeError):
        load_config()


def test_config_legacy_completa(monkeypatch):
    _set_legacy(monkeypatch)
    config = load_config()
    assert isinstance(config, OracleConfig)
    assert config.skipped == []

    conn = config.connections[0]
    assert conn.name == "default"
    assert conn.user == "scott"
    assert conn.password == "tiger"
    assert conn.host == "localhost"
    assert conn.port == 1521
    assert conn.sid == "ORCL"
    assert conn.service_name is None
    assert conn.allow_write is False
    assert conn.max_rows == 200
    assert conn.connect_timeout == 10
    assert conn.pool_min == 1
    assert conn.pool_max == 4

    assert config.default_connection is conn
    assert config.get_connection() is conn
    assert config.get_connection("default") is conn


def test_config_legacy_valores_custom(monkeypatch):
    _set_legacy(
        monkeypatch,
        ORACLE_PORT="1522",
        ORACLE_SERVICE_NAME="XDB",
        ORACLE_ALLOW_WRITE="true",
        ORACLE_MAX_ROWS="500",
        ORACLE_CONNECT_TIMEOUT="30",
        ORACLE_POOL_MIN="2",
        ORACLE_POOL_MAX="8",
    )
    conn = load_config().connections[0]
    assert conn.port == 1522
    assert conn.service_name == "XDB"
    assert conn.sid == "ORCL"  # SID sigue presente; el dsn prefiere SERVICE_NAME
    assert conn.allow_write is True
    assert conn.max_rows == 500
    assert conn.connect_timeout == 30
    assert conn.pool_min == 2
    assert conn.pool_max == 8


def test_config_legacy_faltan_obligatorias(monkeypatch):
    monkeypatch.setenv("ORACLE_USER", "scott")  # sin password ni host
    with pytest.raises(RuntimeError, match="faltan variables obligatorias"):
        load_config()


def test_config_multi_completa(monkeypatch):
    _set_multi(monkeypatch, ["ventas", "logs"])
    config = load_config()
    assert [c.name for c in config.connections] == ["ventas", "logs"]
    assert config.skipped == []
    assert config.default_connection.name == "ventas"
    assert config.connections[1].name == "logs"


def test_config_multi_nombres_minusculas_y_prefijo_upper(monkeypatch):
    _set_multi(monkeypatch, ["MiConex"])
    assert load_config().connections[0].name == "MiConex"


def test_config_multi_omite_incompleta(monkeypatch):
    _set_multi(monkeypatch, ["ok", "mal"])
    monkeypatch.delenv("ORACLE_CONN_MAL_PASSWORD", raising=False)
    config = load_config()
    assert [c.name for c in config.connections] == ["ok"]
    assert config.skipped == ["mal"]
    assert config.default_connection.name == "ok"


def test_config_multi_omite_puerto_invalido(monkeypatch):
    _set_multi(monkeypatch, ["ok", "mal"])
    monkeypatch.setenv("ORACLE_CONN_MAL_PORT", "no-es-puerto")
    config = load_config()
    assert [c.name for c in config.connections] == ["ok"]
    assert config.skipped == ["mal"]


def test_config_multi_configuracion_independiente_por_conexion(monkeypatch):
    _set_multi(monkeypatch, ["rw", "ro"])
    monkeypatch.setenv("ORACLE_CONN_RW_ALLOW_WRITE", "true")
    monkeypatch.setenv("ORACLE_CONN_RW_MAX_ROWS", "500")
    monkeypatch.setenv("ORACLE_CONN_RW_CONNECT_TIMEOUT", "30")
    monkeypatch.setenv("ORACLE_CONN_RW_POOL_MIN", "2")
    monkeypatch.setenv("ORACLE_CONN_RW_POOL_MAX", "8")
    monkeypatch.setenv("ORACLE_CONN_RW_SERVICE_NAME", "XDB")

    config = load_config()
    rw, ro = config.connections

    assert rw.name == "rw"
    assert rw.allow_write is True
    assert rw.max_rows == 500
    assert rw.connect_timeout == 30
    assert rw.pool_min == 2
    assert rw.pool_max == 8
    assert rw.service_name == "XDB"
    assert rw.sid == "ORCL"  # SID sigue presente; el dsn prefiere SERVICE_NAME

    assert ro.name == "ro"
    assert ro.allow_write is False
    assert ro.max_rows == 200
    assert ro.connect_timeout == 10
    assert ro.pool_min == 1
    assert ro.pool_max == 4
    assert ro.service_name is None

    assert config.get_connection("rw") is rw
    assert config.get_connection("ro") is ro


def test_config_multi_todas_incompletas_lanza(monkeypatch):
    _set_multi(monkeypatch, ["a", "b"])
    monkeypatch.delenv("ORACLE_CONN_A_PASSWORD", raising=False)
    monkeypatch.delenv("ORACLE_CONN_B_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="No se pudo cargar ninguna conexion"):
        load_config()


def test_config_multi_vacia_lanza(monkeypatch):
    monkeypatch.setenv("ORACLE_CONNECTIONS", "   ")
    with pytest.raises(RuntimeError, match="definido pero vacio"):
        load_config()


def test_get_connection_inexistente(monkeypatch):
    _set_legacy(monkeypatch)
    config = load_config()
    with pytest.raises(ValueError, match="no encontrada"):
        config.get_connection("otra")


@pytest.mark.parametrize(
    "valor,esperado",
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("off", False),
        ("", False),
    ],
)
def test_bool_env_variantes(monkeypatch, valor, esperado):
    _set_legacy(monkeypatch, ORACLE_ALLOW_WRITE=valor)
    assert load_config().connections[0].allow_write is esperado


def test_bool_env_ausente_default_false(monkeypatch):
    _set_legacy(monkeypatch)
    assert load_config().connections[0].allow_write is False


# ---------------------------------------------------------------------------
# OracleConnectionConfig
# ---------------------------------------------------------------------------


def test_dsn_con_sid():
    conn = make_connection(name="a", host="localhost", port=1521, sid="ORCL")
    dsn = conn.dsn
    assert "HOST=localhost" in dsn
    assert "PORT=1521" in dsn
    assert "SID=ORCL" in dsn
    assert "SERVICE_NAME" not in dsn


def test_dsn_con_service_name():
    conn = make_connection(name="a", sid=None, service_name="XDB")
    assert "SERVICE_NAME=XDB" in conn.dsn
    assert "SID=" not in conn.dsn


def test_dsn_sin_sid_ni_service_lanza():
    conn = make_connection(name="a", sid=None, service_name=None)
    with pytest.raises(RuntimeError, match="ORACLE_SID o ORACLE_SERVICE_NAME"):
        conn.dsn