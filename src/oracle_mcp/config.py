"""Carga y valida la configuracion del servidor a partir de variables de entorno."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _bool_env(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class OracleConfig:
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
            "Debes definir ORACLE_SID o ORACLE_SERVICE_NAME en la configuracion."
        )


def load_config() -> OracleConfig:
    user = os.environ.get("ORACLE_USER")
    password = os.environ.get("ORACLE_PASSWORD")
    host = os.environ.get("ORACLE_HOST")
    port = int(os.environ.get("ORACLE_PORT", "1521"))

    if not user or not password or not host:
        raise RuntimeError(
            "Faltan variables obligatorias: ORACLE_USER, ORACLE_PASSWORD, ORACLE_HOST."
        )

    return OracleConfig(
        user=user,
        password=password,
        host=host,
        port=port,
        sid=os.environ.get("ORACLE_SID") or None,
        service_name=os.environ.get("ORACLE_SERVICE_NAME") or None,
        client_lib_dir=os.environ.get("ORACLE_CLIENT_LIB_DIR") or None,
        allow_write=_bool_env("ORACLE_ALLOW_WRITE", False),
        max_rows=int(os.environ.get("ORACLE_MAX_ROWS", "200")),
        connect_timeout=int(os.environ.get("ORACLE_CONNECT_TIMEOUT", "10")),
        pool_min=int(os.environ.get("ORACLE_POOL_MIN", "1")),
        pool_max=int(os.environ.get("ORACLE_POOL_MAX", "4")),
    )
