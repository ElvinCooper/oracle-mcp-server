"""Helpers compartidos por los tests.

Todo esto funciona SIN conexion a Oracle ni Instant Client: las pruebas de
server.py inyectan pools/cursores falsos, y el resto valida logica pura.
"""

from oracle_mcp.config import OracleConnectionConfig


def make_connection(**overrides) -> OracleConnectionConfig:
    """Crea una conexion valida por defecto, con campos sobrescribibles."""
    defaults = dict(
        name="default",
        user="scott",
        password="tiger",
        host="localhost",
        port=1521,
        sid="ORCL",
        service_name=None,
        client_lib_dir=None,
        allow_write=False,
        max_rows=200,
        connect_timeout=10,
        pool_min=1,
        pool_max=4,
    )
    defaults.update(overrides)
    return OracleConnectionConfig(**defaults)
