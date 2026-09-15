"""Carga y valida la configuracion del servidor a partir de variables de entorno."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger("oracle_mcp.config")

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")


def _bool_env(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class OracleConnectionConfig:
    """Configuracion para una unica conexion a Oracle."""
    name: str
    user: str
    password: str
    host: str
    port: int
    sid: str | None
    service_name: str | None
    client_lib_dir: str | None
    allow_write: bool
    max_rows: int
    connect_timeout: int
    pool_min: int
    pool_max: int

    @property
    def dsn(self) -> str:
        import oracledb

        if self.service_name:
            return oracledb.makedsn(self.host, self.port, service_name=self.service_name)
        if self.sid:
            return oracledb.makedsn(self.host, self.port, sid=self.sid)
        raise RuntimeError(
            f"Conexion '{self.name}': debes definir ORACLE_SID o ORACLE_SERVICE_NAME."
        )


@dataclass(frozen=True)
class OracleConfig:
    """Configuracion principal con soporte para multiples conexiones."""
    connections: list[OracleConnectionConfig]
    skipped: list[str] = field(default_factory=list)

    @property
    def default_connection(self) -> OracleConnectionConfig:
        """Retorna la primera conexion (usada por defecto)."""
        return self.connections[0]

    def get_connection(self, name: str | None = None) -> OracleConnectionConfig:
        """Retorna una conexion por nombre, o la defecto si name es None."""
        if name is None:
            return self.default_connection
        for conn in self.connections:
            if conn.name == name:
                return conn
        available = [c.name for c in self.connections]
        raise ValueError(
            f"Conexion '{name}' no encontrada. Disponibles: {available}"
        )


def _load_connection_config(name: str, prefix: str) -> OracleConnectionConfig:
    """Carga la configuracion de una conexion individual."""
    user = os.environ.get(f"{prefix}_USER")
    password = os.environ.get(f"{prefix}_PASSWORD")
    host = os.environ.get(f"{prefix}_HOST")
    port = int(os.environ.get(f"{prefix}_PORT", "1521"))

    if not user or not password or not host:
        raise RuntimeError(
            f"Conexion '{name}': faltan variables obligatorias: "
            f"{prefix}_USER, {prefix}_PASSWORD, {prefix}_HOST."
        )

    return OracleConnectionConfig(
        name=name,
        user=user,
        password=password,
        host=host,
        port=port,
        sid=os.environ.get(f"{prefix}_SID") or None,
        service_name=os.environ.get(f"{prefix}_SERVICE_NAME") or None,
        client_lib_dir=os.environ.get(f"{prefix}_CLIENT_LIB_DIR") or None,
        allow_write=_bool_env(f"{prefix}_ALLOW_WRITE", False),
        max_rows=int(os.environ.get(f"{prefix}_MAX_ROWS", "200")),
        connect_timeout=int(os.environ.get(f"{prefix}_CONNECT_TIMEOUT", "10")),
        pool_min=int(os.environ.get(f"{prefix}_POOL_MIN", "1")),
        pool_max=int(os.environ.get(f"{prefix}_POOL_MAX", "4")),
    )


def _load_legacy_config() -> OracleConfig:
    """Carga configuracion en formato legacy (una sola conexion)."""
    connection = _load_connection_config("default", "ORACLE")
    return OracleConfig(connections=[connection])


def _load_multi_config() -> OracleConfig:
    """Carga configuracion con multiples conexiones."""
    connections_str = os.environ.get("ORACLE_CONNECTIONS", "")
    connection_names = [n.strip() for n in connections_str.split(",") if n.strip()]

    if not connection_names:
        raise RuntimeError(
            "ORACLE_CONNECTIONS esta definido pero vacio. "
            "Formato: ORACLE_CONNECTIONS=conn1,conn2,conn3"
        )

    connections = []
    skipped = []
    for name in connection_names:
        prefix = f"ORACLE_CONN_{name.upper()}"
        try:
            conn = _load_connection_config(name, prefix)
        except (RuntimeError, ValueError) as exc:
            logger.warning(
                "Conexion '%s' omitida por configuracion incompleta: %s", name, exc
            )
            skipped.append(name)
            continue
        connections.append(conn)

    if not connections:
        raise RuntimeError(
            "No se pudo cargar ninguna conexion. "
            f"Omitidas por configuracion incompleta: {', '.join(skipped)}"
        )

    return OracleConfig(connections=connections, skipped=skipped)


def load_config() -> OracleConfig:
    """Carga la configuracion detectando automaticamente el formato."""
    if os.environ.get("ORACLE_CONNECTIONS"):
        return _load_multi_config()
    elif os.environ.get("ORACLE_USER"):
        return _load_legacy_config()
    else:
        raise RuntimeError(
            "No se encontro configuracion de Oracle. "
            "Define ORACLE_CONNECTIONS (multi-conexion) o ORACLE_USER (legacy)."
        )
