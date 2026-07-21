from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.configs import settings
from app.models import __all_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# A URL vem do ambiente; nenhuma credencial é persistida no alembic.ini.
config.set_main_option("sqlalchemy.url", settings.database_url_sync.replace("%", "%%"))

target_metadata = settings.DBBaseModel.metadata


def run_migrations_offline() -> None:
    """Gera SQL sem abrir uma conexão com o banco."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Executa migrations usando uma conexão síncrona dedicada."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

