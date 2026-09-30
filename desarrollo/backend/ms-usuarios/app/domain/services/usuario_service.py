from app.domain.ports.usuario_repository_port import UsuarioRepositoryPort
from app.domain.models.usuario import UsuarioModel
from app.schemas.schema_usuario import CrearUsuarioSchema

class UsuarioService:
    def __init__(self, repository: UsuarioRepositoryPort):
        self.repository = repository

    def obtener_o_crear_usuario(self, azure_oid: str, email: str, rol_azure: str = "CLIENTE") -> UsuarioModel:
        usuario = self.repository.get_by_azure_oid(azure_oid)

        if not usuario:
            nuevo_usuario = CrearUsuarioSchema(
                azure_oid=azure_oid,
                email=email,
                rol=rol_azure
            )
            usuario = self.repository.create(nuevo_usuario)
            return usuario

        # El usuario ya existe: sincronizamos el rol local con el rol
        # que Azure AD reporta en el token en cada login/consulta.
        if usuario.rol != rol_azure:
            usuario = self.repository.actualizar_rol(usuario, rol_azure)

        return usuario