#!/usr/bin/env bash
# Fija o elimina las credenciales (USER/PASSWORD) de una conexion Oracle
# como variables de entorno del usuario (via ~/.bashrc), evitando guardarlas
# en texto plano en el .env.
#
# Uso:
#   ./set-secrets.sh <nombre_conexion>              Fija usuario y password de forma interactiva
#   ./set-secrets.sh <nombre_conexion> <usuario>    Fija el usuario (pide password)
#   ./set-secrets.sh <nombre_conexion> --unset      Elimina las credenciales
#
# El resultado se agrega a $RCFILE (por defecto ~/.bashrc). Puedes cambiarlo
# con RCFILE=/ruta ./set-secrets.sh <nombre_conexion> <usuario>.
set -euo pipefail

RCFILE="${RCFILE:-$HOME/.bashrc}"
NAME="${1:-}"
MODE="${2:-}"

usage() {
    cat <<EOF
Uso:
  $0 <nombre_conexion>              Fija usuario y password de forma interactiva
  $0 <nombre_conexion> <usuario>    Fija el usuario (pide password)
  $0 <nombre_conexion> --unset      Elimina las credenciales

El resultado se agrega a $RCFILE (o usa RCFILE=/ruta para cambiarlo).
EOF
    exit 1
}

[[ -z "$NAME" ]] && usage

PREFIX="ORACLE_CONN_$(echo "$NAME" | tr '[:lower:]' '[:upper:]')"
USER_VAR="${PREFIX}_USER"
PASS_VAR="${PREFIX}_PASSWORD"

set_secret() {
    local var="$1" value="$2"
    if grep -q "^export ${var}=" "$RCFILE" 2>/dev/null; then
        sed -i "s|^export ${var}=.*|export ${var}=\"${value}\"|" "$RCFILE"
    else
        echo "export ${var}=\"${value}\"" >> "$RCFILE"
    fi
}

unset_secret() {
    local var="$1"
    sed -i "/^export ${var}=/d" "$RCFILE"
}

if [[ "$MODE" == "--unset" ]]; then
    unset_secret "$USER_VAR"
    unset_secret "$PASS_VAR"
    echo "[OK] Credenciales de '$NAME' eliminadas de $RCFILE"
    exit 0
fi

USERNAME="$MODE"
if [[ -z "$USERNAME" ]]; then
    read -rp "Usuario para '$NAME': " USERNAME
fi

read -rsp "Password para '$NAME': " PASSWORD
echo

if [[ -z "$USERNAME" || -z "$PASSWORD" ]]; then
    echo "Error: usuario y password son obligatorios." >&2
    exit 1
fi

set_secret "$USER_VAR" "$USERNAME"
set_secret "$PASS_VAR" "$PASSWORD"

echo "[OK] Credenciales de '$NAME' guardadas en $RCFILE"
echo "Recarga la configuracion y reinicia el cliente MCP: source $RCFILE"
