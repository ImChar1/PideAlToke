import jwt
from jwt import PyJWKClient, ExpiredSignatureError, InvalidTokenError
from fastapi import HTTPException, Security, status, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.config import settings

security_scheme = HTTPBearer()

# URL de descubrimiento JWKS de Azure Entra ID
JWKS_URL = f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}/discovery/v2.0/keys"
jwk_client = PyJWKClient(JWKS_URL)

def get_current_user_claims(credentials: HTTPAuthorizationCredentials = Security(security_scheme)) -> dict:
    token = credentials.credentials

    # Audiencias válidas (soporta UUID directo o URI con prefijo api://)
    valid_audiences = [
        settings.AZURE_CLIENT_ID,
        f"api://{settings.AZURE_CLIENT_ID}"
    ]

    # Emisores válidos (v2.0 y v1.0 / STS)
    valid_issuers = [
        f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}/v2.0",
        f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/"
    ]

    try:
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=valid_audiences,
            issuer=valid_issuers
        )
        return payload

    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token JWT ha expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token JWT no válido: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Error al procesar la firma del token con Azure AD.",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Función para extraer el string crudo del token y reenviarlo a otros microservicios
def get_raw_token(credentials: HTTPAuthorizationCredentials = Security(security_scheme)) -> str:
    return credentials.credentials

# Validación opcional de Scopes/Ámbitos (Equivalente al @PreAuthorize de la guía)
def require_scope(required_scope: str):
    def scope_checker(claims: dict = Depends(get_current_user_claims)):
        scopes = claims.get("scp", "").split(" ")
        if required_scope not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso insuficiente. Requiere el ámbito: {required_scope}"
            )
        return claims
    return scope_checker