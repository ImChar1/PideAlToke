# Microservicio de Usuarios (`ms-usuarios`) - PideAlToke

Registra y sincroniza a cada persona que inicia sesion con **Azure Entra ID**. No guarda contrasenas: la identidad real es el `azure_oid` del token; aqui solo se mantiene el perfil local (correo, rol, estado).

## Endpoint

| Metodo | Ruta | Descripcion |
|---|---|---|
| GET | `/api/v1/users/me` | Devuelve el usuario del token. En el primer login lo crea; en los siguientes sincroniza su rol |

- El rol sale del claim `roles` del token: `ADMIN` si trae ese App Role, `CLIENTE` en cualquier otro caso.
- El identificador es el claim `oid` (o `sub` si no hay `oid`). Sin ninguno de los dos responde 400.
- El correo se toma de `preferred_username`, `email` o `upn` (el primero con formato valido). Si ninguno sirve, el usuario se registra igual **sin correo** (`email: null`).
- Dos peticiones simultaneas del mismo usuario no fallan: la que pierde la carrera recibe el usuario ya creado. Un correo ya usado por *otro* usuario responde 409.

## Configuracion

Ver `.env.example`. `AZURE_TENANT_ID` y `AZURE_CLIENT_ID` son **obligatorios**: sin ellos el servicio se niega a arrancar con un mensaje claro (antes respondia 401 confusos).

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Usan una SQLite temporal (no necesitan `.env` ni Docker). Para correrlos contra una MariaDB real define `TEST_DATABASE_URL`.

## Docker

```bash
docker build -t ms-usuarios .
docker run --env-file .env -p 8001:8000 ms-usuarios
```

El contenedor escucha en el puerto **8000** (compose y Terraform lo publican en el 8001). La imagen solo contiene `app/`: nunca lleva `.env` ni bases locales.
