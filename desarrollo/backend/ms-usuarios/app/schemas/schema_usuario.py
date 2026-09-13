from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime

class UsuarioBaseSchema(BaseModel):
    email: EmailStr
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