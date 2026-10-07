# Configuracion comun de tests: se ejecuta ANTES de importar app.main, asi los tests
# no dependen de un .env local ni tocan una base de datos real.
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="pidealtoke-tests-")
# Se fuerza (no setdefault): los tests nunca deben apuntar a una DB real aunque haya
# un DATABASE_URL exportado en la terminal.
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ.setdefault("AZURE_TENANT_ID", "test-tenant")
os.environ.setdefault("AZURE_CLIENT_ID", "test-client")
