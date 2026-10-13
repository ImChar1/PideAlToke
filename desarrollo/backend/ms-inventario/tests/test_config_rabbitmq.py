# Con RABBITMQ_ENABLED=true las credenciales son obligatorias: el servicio debe negarse a arrancar.

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _importar_config(**env_extra):
    env = {
        **os.environ,
        "DATABASE_URL": "sqlite:///./no-se-usa.db",
        "AZURE_TENANT_ID": "tenant",
        "AZURE_CLIENT_ID": "client",
        **env_extra,
    }
    return subprocess.run(
        [sys.executable, "-c", "import app.core.config"],
        cwd=RAIZ, env=env, capture_output=True, text=True,
    )


def test_arranca_con_rabbitmq_apagado_y_sin_credenciales():
    r = _importar_config(RABBITMQ_ENABLED="false", RABBITMQ_USER="", RABBITMQ_PASSWORD="")
    assert r.returncode == 0, r.stderr


def test_arranca_con_rabbitmq_encendido_y_credenciales():
    r = _importar_config(RABBITMQ_ENABLED="true", RABBITMQ_USER="u", RABBITMQ_PASSWORD="p")
    assert r.returncode == 0, r.stderr


def test_no_arranca_con_rabbitmq_encendido_sin_credenciales():
    r = _importar_config(RABBITMQ_ENABLED="true", RABBITMQ_USER="", RABBITMQ_PASSWORD="")
    assert r.returncode != 0 and "RABBITMQ_USER" in r.stderr
