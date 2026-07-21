"""Create baseline data schema.

Revision ID: 20260721_01
Revises:
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the extension and tables required by the data pipeline."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "responsavel",
        sa.Column("nis_responsavel", sa.String(), nullable=False),
        sa.Column("cpf_responsavel", sa.String(), nullable=True),
        sa.Column("nome_responsavel", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("nis_responsavel"),
    )

    op.create_table(
        "beneficiario",
        sa.Column("nis_beneficiario", sa.String(), nullable=False),
        sa.Column("cpf_beneficiario", sa.String(), nullable=True),
        sa.Column("nome_beneficiario", sa.String(), nullable=True),
        sa.Column("uf", sa.String(length=2), nullable=True),
        sa.Column("codigo_ibge_municipio", sa.Integer(), nullable=True),
        sa.Column("municipio", sa.Text(), nullable=True),
        sa.Column("nis_responsavel", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["nis_responsavel"],
            ["responsavel.nis_responsavel"],
        ),
        sa.PrimaryKeyConstraint("nis_beneficiario"),
    )

    op.create_table(
        "auxilio",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ano_mes", sa.String(length=6), nullable=True),
        sa.Column("enquadramento", sa.Text(), nullable=True),
        sa.Column("parcela", sa.Integer(), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("valor", sa.Float(), nullable=True),
        sa.Column("nis_beneficiario", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["nis_beneficiario"],
            ["beneficiario.nis_beneficiario"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Remove the baseline schema in reverse dependency order."""
    op.drop_table("auxilio")
    op.drop_table("beneficiario")
    op.drop_table("responsavel")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")

