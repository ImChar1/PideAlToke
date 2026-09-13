from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.security import get_current_user_claims
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.usuario_repository import UsuarioRepository
from app.domain.services.usuario_service import UsuarioService
from app.schemas.schema_usuario import UsuarioResponseSchema

router = APIRouter(prefix="/users", tags=["Usuarios"])

@router.get("/me", response_model=UsuarioResponseSchema)
def get_or_create_current_user(
    claims: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db)
):
    azure_oid = claims.get("oid") or claims.get("sub")
    
    if not azure_oid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El token JWT no contiene un identificador único válido (oid/sub)."
        )

    email = claims.get("preferred_username") or claims.get("email", "")

    # Inyección Hexagonal: Router -> Service -> Repository
    repository = UsuarioRepository(db)
    service = UsuarioService(repository)

    try:
        return service.obtener_o_crear_usuario(azure_oid=azure_oid, email=email)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario registrado con este correo electrónico."
        )