from datetime import datetime, timezone
from types import SimpleNamespace

from app.domain.ports.usuario_repository_port import UsuarioRepositoryPort
from app.domain.services.usuario_service import UsuarioService


class FakeUsuarioRepository(UsuarioRepositoryPort):
    def __init__(self):
        self.data = {}

    def get_by_azure_oid(self, azure_oid):
        return self.data.get(azure_oid)

    def create(self, usuario_data):
        u = SimpleNamespace(id=len(self.data) + 1, activo=True,
                            fecha_creacion=datetime.now(timezone.utc),
                            **usuario_data.model_dump())
        self.data[u.azure_oid] = u
        return u

    def actualizar_rol(self, usuario, nuevo_rol):
        usuario.rol = nuevo_rol
        return usuario


def test_primer_login_crea_el_usuario_con_el_rol_de_azure():
    service = UsuarioService(FakeUsuarioRepository())
    u = service.obtener_o_crear_usuario("oid-1", "ana@example.com", "ADMIN")
    assert u.azure_oid == "oid-1" and u.rol == "ADMIN"


def test_segundo_login_reutiliza_el_usuario_existente():
    repo = FakeUsuarioRepository()
    service = UsuarioService(repo)
    a = service.obtener_o_crear_usuario("oid-1", "ana@example.com", "CLIENTE")
    b = service.obtener_o_crear_usuario("oid-1", "ana@example.com", "CLIENTE")
    assert a is b and len(repo.data) == 1


def test_el_rol_local_se_sincroniza_con_el_de_azure():
    service = UsuarioService(FakeUsuarioRepository())
    service.obtener_o_crear_usuario("oid-1", "ana@example.com", "CLIENTE")
    u = service.obtener_o_crear_usuario("oid-1", "ana@example.com", "ADMIN")
    assert u.rol == "ADMIN"
