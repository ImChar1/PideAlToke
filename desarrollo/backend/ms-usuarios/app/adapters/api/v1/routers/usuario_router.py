from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user_claims
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.usuario_repository import UsuarioRepository
from app.schemas.schema_usuario import CrearUsuarioSchema, UsuarioResponseSchema

router = APIRouter(prefix="/users", tags=["Usuarios"])
repo = UsuarioRepository()

@router.get("/me", response_model=UsuarioResponseSchema)
def get_or_create_current_user(
    claims: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db)
):
    azure_oid = claims.get("oid") or claims.get("sub")
    email = claims.get("preferred_username") or claims.get("email", "")

    usuario = repo.get_by_azure_oid(db, azure_oid)
    if not usuario:
        nuevo_usuario = CrearUsuarioSchema(
            azure_oid=azure_oid,
            email=email,
            nombre_completo=claims.get("name", "Usuario"),
            rol="CLIENTE"
        )
        usuario = repo.create(db, nuevo_usuario)
    
    return usuario