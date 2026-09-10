# Valida el JWT emitido por Azure AD (IDaaS) antes de autorizar cualquier peticion.
# Cumple lo pedido en la pauta para el BFF: valida firma (JWKS/RS256), issuer, audience
# y aplica autorizacion por rol (RBAC), respondiendo con codigos de error adecuados.
#
# NOTA: replicar/compartir esta logica con ms-pedidos y ms-usuarios para no duplicar
# la validacion JWT en cada microservicio.

from typing import Optional

import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from app.core.config import settings

bearer_scheme = HTTPBearer()

_JWKS_CACHE: Optional[dict] = None


def _get_jwks() -> dict:
    """Descarga (y cachea en memoria del proceso) las claves publicas JWKS de Azure AD."""
    global _JWKS_CACHE
    if _JWKS_CACHE is None:
        jwks_url = (
            f"https://login.microsoftonline.com/"
            f"{settings.AZURE_TENANT_ID}/discovery/v2.0/keys"
        )
        response = requests.get(jwks_url, timeout=5)
        response.raise_for_status()
        _JWKS_CACHE = response.json()
    return _JWKS_CACHE


def validar_jwt(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Valida firma (RS256), issuer, audience y vigencia del token.
    Devuelve los claims decodificados si es valido; lanza 401 si no lo es.
    """
    token = credentials.credentials

    try:
        jwks = _get_jwks()
        unverified_header = jwt.get_unverified_header(token)

        rsa_key = next(
            (
                {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
                for key in jwks.get("keys", [])
                if key["kid"] == unverified_header.get("kid")
            ),
            None,
        )
        if rsa_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No se encontro una clave JWKS que coincida con el token.",
            )

        claims = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=settings.AZURE_CLIENT_ID,
            issuer=f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}/v2.0",
        )
        return claims

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token invalido o expirado: {str(e)}",
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No fue posible validar el token contra el IDaaS (Azure AD).",
        )


def requerir_rol(rol_esperado: str):
    """
    Dependencia factory para RBAC: exige que el JWT ya validado contenga el rol/claim
    esperado (ej. 'ADMIN') antes de dejar pasar la peticion. Usar en endpoints de escritura.
    """

    def _verificar(claims: dict = Depends(validar_jwt)) -> dict:
        roles = claims.get("roles", []) or claims.get("scp", "").split(" ")
        if rol_esperado not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Se requiere el rol '{rol_esperado}' para esta operacion.",
            )
        return claims

    return _verificar
