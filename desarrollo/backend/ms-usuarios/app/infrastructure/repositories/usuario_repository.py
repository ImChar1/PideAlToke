from sqlalchemy import select
from sqlalchemy.orm import Session
from app.domain.ports.usuario_repository_port import UsuarioRepositoryPort
from app.domain.models.usuario import UsuarioModel
from app.schemas.schema_usuario import CrearUsuarioSchema

class UsuarioRepository(UsuarioRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    def get_by_azure_oid(self, azure_oid: str) -> UsuarioModel | None:
        stmt = select(UsuarioModel).where(UsuarioModel.azure_oid == azure_oid)
        return self.db.scalars(stmt).first()

    def create(self, usuario_data: CrearUsuarioSchema) -> UsuarioModel:
        db_usuario = UsuarioModel(**usuario_data.model_dump(exclude_unset=True))
        self.db.add(db_usuario)
        self.db.commit()
        self.db.refresh(db_usuario)
        return db_usuario