#Implementación de acceso a datos con SQLAlchemy
from sqlalchemy.orm import Session
from app.domain.models.usuario import UsuarioModel
from app.schemas.schema_usuario import CrearUsuarioSchema

class UsuarioRepository:
    def get_by_azure_oid(self, db: Session, azure_oid: str) -> UsuarioModel | None:
        return db.query(UsuarioModel).filter(UsuarioModel.azure_oid == azure_oid).first()

    def create(self, db: Session, usuario_data: CrearUsuarioSchema) -> UsuarioModel:
        db_usuario = UsuarioModel(
            azure_oid=usuario_data.azure_oid,
            email=usuario_data.email,
            rol=usuario_data.rol
        )
        db.add(db_usuario)
        db.commit()
        db.refresh(db_usuario)
        return db_usuario