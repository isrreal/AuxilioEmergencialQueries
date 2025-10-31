from pytz import timezone
from typing import Optional, Dict
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt
from pydantic import EmailStr

from app.core.configs import settings
from app.core.security import verificar_senha

from app.models.models import Usuario


oauth2_schema = OAuth2PasswordBearer(tokenUrl = f"{settings.API_V1_STR}/login")

async def autenticar(email: EmailStr, senha: str, db: AsyncSession) -> Optional[Usuario]:
    """
    Verifica as credenciais de um usuário no banco de dados.

    Busca um usuário pelo email e compara a senha fornecida (em texto plano)
    com o hash armazenado no banco de dados usando a função `verificar_senha`.

    Args:
        email (EmailStr): O email do usuário a ser autenticado.
        senha (str): A senha em texto plano a ser verificada.
        db (AsyncSession): A sessão assíncrona do SQLAlchemy para consulta.

    Returns:
        Optional[Usuario]: O objeto `UsuarioModel` correspondente se
            as credenciais estiverem corretas. Retorna `None` caso o email
            não seja encontrado ou a senha esteja incorreta.
    """
    async with db as session:
        query = select(Usuario).filter(Usuario.email == email)
        result = await session.execute(query)
        usuario: Usuario = result.scalars().unique().one_or_none()
        
        if not usuario:
            return None
        if not verificar_senha(senha, usuario.senha):
            return None

        return usuario



def _criar_token(tipo_token: str, tempo_vida: timedelta, sub: str) -> str:
    """
    Cria um token JWT.
    
    Args:
        tipo_token: Tipo do token (ex: 'access_token')
        tempo_vida: Tempo de vida do token
        sub: Subject (geralmente o ID do usuário)
        
    Returns:
        str: Token JWT codificado
    """
    fortaleza = timezone("America/Fortaleza")
    expira = datetime.now(tz = fortaleza) + tempo_vida
    
    payload = {
        "type": tipo_token,
        "exp": expira,
        "iat": datetime.now(tz = fortaleza),
        "sub": str(sub),
    }
    
    return jwt.encode(
        payload, 
        settings.JWT_SECRET, 
        algorithm = settings.ALGORITHM
    )


def criar_token_acesso(sub: str) -> str:
    """
    Cria um token de acesso JWT.
    
    Args:
        sub: Subject (ID do usuário ou identificador único)
        
    Returns:
        str: Token de acesso JWT
    """
    return _criar_token(
        tipo_token = "access_token",
        tempo_vida = timedelta(minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        sub = sub
    )


def criar_token_refresh(sub: str) -> str:
    """
    Cria um token de refresh (vida mais longa).
    
    Args:
        sub: Subject (ID do usuário)
        
    Returns:
        str: Token de refresh JWT
    """
    return _criar_token(
        tipo_token = "refresh_token",
        tempo_vida = timedelta(days = 30), 
        sub = sub
    )


def decodificar_token(token: str) -> dict:
    """
    Decodifica e valida um token JWT.
    
    Args:
        token: Token JWT a ser decodificado
        
    Returns:
        dict: Payload do token
        
    Raises:
        JWTError: Se o token for inválido ou expirado
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms = [settings.ALGORITHM],
        options = {"verify_aud": False}
    )

def validar_tipo_token(payload: Dict, tipo_esperado: str) -> bool:
    """
    Valida se o token é do tipo esperado.
    
    Args:
        payload: Payload decodificado do token
        tipo_esperado: Tipo esperado (ex: 'access_token')
        
    Returns:
        bool: True se o tipo corresponder
    """
    return payload.get("type") == tipo_esperado


def extrair_user_id(payload: Dict) -> Optional[str]:
    """
    Extrai o ID do usuário do payload do token.
    
    Args:
        payload: Payload decodificado do token
        
    Returns:
        str: ID do usuário ou None
    """
    return payload.get("sub")


def token_expirado(payload: Dict) -> bool:
    """
    Verifica se o token está expirado.
    
    Args:
        payload: Payload decodificado do token
        
    Returns:
        bool: True se expirado
    """
    exp = payload.get("exp")
    if not exp:
        return True
    
    fortaleza = timezone("America/Fortaleza")
    exp_datetime = datetime.fromtimestamp(exp, tz = fortaleza)
    return datetime.now(tz = fortaleza) > exp_datetime