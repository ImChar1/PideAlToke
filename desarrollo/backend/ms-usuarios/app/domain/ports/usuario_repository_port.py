from abc import ABC, abstractmethod
from app.domain.models.usuario import UsuarioModel
from app.schemas.schema_usuario import CrearUsuarioSchema

class UsuarioRepositoryPort(ABC):
    @abstractmethod
    def get_by_azure_oid(self, azure_oid: str) -> UsuarioModel | None:
        pass

    @abstractmethod
    def create(self, usuario_data: CrearUsuarioSchema) -> UsuarioModel:
        pass

    @abstractmethod
    def actualizar_rol(self, usuario: UsuarioModel, nuevo_rol: str) -> UsuarioModel:
        pass