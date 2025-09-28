"""Agregar columna categoria a movimientos_caja

Revision ID: 7e3be27d6e65
Revises: f7cf2e57d852
Create Date: 2025-09-28 16:37:55.821184

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7e3be27d6e65'
down_revision = 'f7cf2e57d852'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar columna 'categoria' con valor por defecto 'general'
    with op.batch_alter_table('movimientos_caja', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('categoria', sa.String(length=20), nullable=False, server_default="general")
        )


def downgrade():
    # Eliminar columna 'categoria' si se revierte la migración
    with op.batch_alter_table('movimientos_caja', schema=None) as batch_op:
        batch_op.drop_column('categoria')
