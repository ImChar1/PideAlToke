import jwt
from jwt import PyJWKClient, ExpiredSignatureError, InvalidTokenError
from fastapi import HTTPException, Security, status, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.config import settings

security_scheme = HTTPBearer()

JWKS_URL = f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}/discovery/v2.0/keys"
jwk_client = PyJWKClient(JWKS_URL)

def validar_jwt(credentials: HTTPAuthorizationCredentials = Security(security_scheme)) -> dict:
    token = credentials.credentials
    valid_audiences = [settings.AZURE_CLIENT_ID, f"api://{settings.AZURE_CLIENT_ID}"]
    valid_issuers = [
        f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}/v2.0",
        f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/"
    ]

    try:
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=valid_audiences,
            issuer=valid_issuers
        )
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="El token ha expirado.")
    except InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token inválido: {str(e)}")
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Error al validar el token con Azure AD.")

def requerir_rol(rol_requerido: str):
    def role_checker(claims: dict = Depends(validar_jwt)):
        roles = claims.get("roles", [])
        if rol_requerido not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requiere el rol: {rol_requerido}"
            )
        return claims
    return role_checker