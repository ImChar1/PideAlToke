from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime

class UsuarioBaseSchema(BaseModel):
    # Opcional: no todos los tokens de Azure traen un correo (cuentas sin buzon, invitados,
    # preferred_username con formato de UPN no valido). La identidad real es azure_oid.
    email: Optional[EmailStr] = None
    rol: str = "CLIENTE"

class CrearUsuarioSchema(UsuarioBaseSchema):
    azure_oid: str

class UsuarioResponseSchema(UsuarioBaseSchema):
    id: int
    azure_oid: str
    activo: bool
    fecha_creacion: datetime

    # Permite mapear directamente objetos SQLAlchemy a JSON
    model_config = ConfigDict(from_attributes=True)