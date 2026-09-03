from pydantic import BaseModel, EmailStr
from datetime import datetime

class UsuarioBaseSchema(BaseModel):
    email: EmailStr
    nombre_completo: str
    rol: str = "CLIENTE" # Para control de roles

class CrearUsuarioSchema(UsuarioBaseSchema):
    azure_oid: str # ID del usuario proviniente de Azure AD

class UsuarioResponseSchema(UsuarioBaseSchema):
    id: int
    azure_oid: str
    activo: bool
    fecha_creacion: datetime

class Config:
    from_attributes = True