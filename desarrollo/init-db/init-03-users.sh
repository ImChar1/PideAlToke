#!/bin/bash
# Crea un usuario de base de datos POR MICROSERVICIO, con permisos solo sobre SU base.
#
# Antes los 4 servicios se conectaban como root: si uno se veia comprometido (o tenia un
# bug de SQL), podia leer/borrar las bases de los demas. Ahora cada uno solo ve la suya y
# no puede hacer DROP ni administrar usuarios.
#
# Lo ejecuta el entrypoint de MariaDB UNA SOLA VEZ, al crear el volumen de datos (igual que
# los .sql de esta carpeta). Recibe las contrasenas por variables de entorno:
#   DB_PASS_USUARIOS, DB_PASS_CATALOGO, DB_PASS_INVENTARIO, DB_PASS_PEDIDOS
# Funciona tanto si el entrypoint lo ejecuta como si lo "sourcea" (bind mount sin permiso +x).
# Los nombres de base coinciden con los de init-01.sql.

ROOT_PW="${MARIADB_ROOT_PASSWORD:-${MYSQL_ROOT_PASSWORD:-}}"

# Escapa \ y ' para usar la contrasena dentro de un literal SQL entre comillas simples.
_sql_escape() {
  local v="${1//\\/\\\\}"
  printf '%s' "${v//\'/\'\'}"
}

_crear_usuario_servicio() {
  local usuario="$1" base="$2" clave="$3"
  if [ -z "$clave" ]; then
    echo "[init-03-users] ERROR: falta la contrasena de ${usuario} (variable DB_PASS_*)." >&2
    return 1
  fi
  local clave_sql
  clave_sql="$(_sql_escape "$clave")"

  # MYSQL_PWD evita pasar la contrasena de root como argumento (visible en la lista de procesos).
  MYSQL_PWD="$ROOT_PW" mariadb -uroot <<SQL
CREATE USER IF NOT EXISTS '${usuario}'@'%' IDENTIFIED BY '${clave_sql}';
ALTER USER '${usuario}'@'%' IDENTIFIED BY '${clave_sql}';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES ON \`${base}\`.* TO '${usuario}'@'%';
SQL
}

_crear_usuario_servicio svc_usuarios   usuarios_db   "${DB_PASS_USUARIOS:-}"   || exit 1
_crear_usuario_servicio svc_catalogo   catalogo_db   "${DB_PASS_CATALOGO:-}"   || exit 1
_crear_usuario_servicio svc_inventario inventario_db "${DB_PASS_INVENTARIO:-}" || exit 1
_crear_usuario_servicio svc_pedidos    pedidos_db    "${DB_PASS_PEDIDOS:-}"    || exit 1

echo "[init-03-users] Usuarios por microservicio creados."
