from typing import ClassVar, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.decl_api import DeclarativeMeta


class Settings(BaseSettings):
    """
    Configurações da aplicação.
    
    As variáveis são carregadas do arquivo .env ou das variáveis de ambiente.
    """
    
    # API
    API_V1_STR: str = '/api/v1'
    PROJECT_NAME: str = 'Emergencial Aid API'
    VERSION: str = '1.0.0'
    DESCRIPTION: str = 'API para gerenciamento de auxílios emergenciais'
    
    # Database
    DATABASE_URL: str
    DB_ECHO: bool = False  # Log de queries SQL (True para debug)
    
    # SQLAlchemy Base
    DBBaseModel: ClassVar[DeclarativeMeta] = declarative_base()
    
    # Security - JWT
    JWT_SECRET: str = 'LOB-VggKMl1pDElBfgQsbFq1w72x1aCswhbaayFthEQ'
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 dias
    
    # CORS
    BACKEND_CORS_ORIGINS: list = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8080",
    ]
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 100
    MAX_PAGE_SIZE: int = 1000
    
    # File paths (para importação de dados)
    DATA_DIR: str = '/data'
    UPLOAD_DIR: str = '/app/uploads'
    
    # Postgres específico
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None
    POSTGRES_HOST: Optional[str] = None
    POSTGRES_PORT: Optional[int] = 5432
    
    # Configuração do Pydantic Settings
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore'  # Ignora variáveis extras do .env
    )
    
    @property
    def database_url_sync(self) -> str:
        """
        URL do banco para operações síncronas (ex: Alembic).
        Converte asyncpg para psycopg2.
        """
        return self.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
    
    @property
    def is_development(self) -> bool:
        """Verifica se está em ambiente de desenvolvimento."""
        return 'localhost' in self.DATABASE_URL or '127.0.0.1' in self.DATABASE_URL


settings = Settings()