from typing import Optional

from email_validator import validate_email, EmailNotValidError
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.security import get_current_user_claims
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.usuario_repository import UsuarioRepository
from app.domain.services.usuario_service import UsuarioService
from app.schemas.schema_usuario import UsuarioResponseSchema

router = APIRouter(prefix="/users", tags=["Usuarios"])


def _extraer_email(claims: dict) -> Optional[str]:
    """
    Primer claim con forma de correo valido (preferred_username, email o upn).
    Si ninguno sirve devuelve None en vez de romper con un 500: el usuario se
    registra igual (se identifica por azure_oid) y queda sin correo.
    """
    for clave in ("preferred_username", "email", "upn"):
        valor = claims.get(clave)
        if not valor:
            continue
        try:
            return validate_email(valor, check_deliverability=False).normalized
        except EmailNotValidError:
            continue
    return None

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

    email = _extraer_email(claims)

    # El App Role asignado en Azure AD viaja en el claim "roles" (array).
    # Si el usuario tiene el rol "ADMIN" asignado en Azure Portal -> Enterprise
    # Application -> Usuarios y grupos, se refleja aqui; en caso contrario,
    # se trata como CLIENTE por defecto.
    azure_roles = claims.get("roles", [])
    rol_azure = "ADMIN" if "ADMIN" in azure_roles else "CLIENTE"

    # Inyección Hexagonal: Router -> Service -> Repository
    repository = UsuarioRepository(db)
    service = UsuarioService(repository)

    try:
        return service.obtener_o_crear_usuario(azure_oid=azure_oid, email=email, rol_azure=rol_azure)
    except IntegrityError:
        db.rollback()
        # Puede ser una carrera: dos peticiones simultaneas del MISMO usuario (ej. el
        # frontend llama /me dos veces al iniciar) intentan crearlo a la vez y una pierde
        # contra la restriccion UNIQUE de azure_oid. En ese caso el usuario ya existe: se
        # devuelve en vez de fallar.
        if repository.get_by_azure_oid(azure_oid):
            return service.obtener_o_crear_usuario(azure_oid=azure_oid, email=email, rol_azure=rol_azure)
        # Si no existe, el conflicto es de verdad por el correo (otro azure_oid ya lo usa).
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario registrado con este correo electrónico."
        )
