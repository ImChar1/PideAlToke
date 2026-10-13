# La configuracion de Azure y de RabbitMQ es obligatoria: sin ella el servicio debe negarse a arrancar.

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _importar_config(**env_extra):
    env = {
        **os.environ,
        "AZURE_TENANT_ID": "tenant",
        "AZURE_CLIENT_ID": "client",
        "RABBITMQ_USER": "u",
        "RABBITMQ_PASSWORD": "p",
        **env_extra,
    }
    return subprocess.run(
        [sys.executable, "-c", "import app.core.config"],
        cwd=RAIZ, env=env, capture_output=True, text=True,
    )


def test_arranca_con_la_configuracion_completa():
    r = _importar_config()
    assert r.returncode == 0, r.stderr


def test_ignora_variables_rabbitmq_de_otros_servicios():
    # docker compose inyecta RABBITMQ_ENABLED a todos los servicios; este no lo usa pero no debe fallar.
    r = _importar_config(RABBITMQ_ENABLED="true")
    assert r.returncode == 0, r.stderr


def test_no_arranca_sin_tenant_id():
    r = _importar_config(AZURE_TENANT_ID="")
    assert r.returncode != 0 and "AZURE_TENANT_ID" in r.stderr


def test_no_arranca_sin_credenciales_de_rabbitmq():
    r = _importar_config(RABBITMQ_USER="", RABBITMQ_PASSWORD="")
    assert r.returncode != 0 and "RABBITMQ_USER" in r.stderr
