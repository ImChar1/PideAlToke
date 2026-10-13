# La configuracion de Azure es obligatoria: sin ella el servicio debe negarse a arrancar.

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _importar_config(**env_extra):
    env = {**os.environ, "DATABASE_URL": "sqlite:///./no-se-usa.db", **env_extra}
    return subprocess.run(
        [sys.executable, "-c", "import app.core.config"],
        cwd=RAIZ, env=env, capture_output=True, text=True,
    )


def test_arranca_si_estan_los_datos_de_azure():
    r = _importar_config(AZURE_TENANT_ID="tenant", AZURE_CLIENT_ID="client")
    assert r.returncode == 0, r.stderr


def test_no_arranca_sin_tenant_id():
    r = _importar_config(AZURE_TENANT_ID="", AZURE_CLIENT_ID="client")
    assert r.returncode != 0 and "AZURE_TENANT_ID" in r.stderr


def test_no_arranca_sin_client_id():
    r = _importar_config(AZURE_TENANT_ID="tenant", AZURE_CLIENT_ID="")
    assert r.returncode != 0 and "AZURE_CLIENT_ID" in r.stderr
