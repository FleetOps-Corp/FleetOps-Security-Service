"""add new system role

Revision ID: 002
Revises: 001
Create Date: 2026-07-06 00:00:00.000000
"""
from datetime import datetime, timezone

import sqlalchemy as sa

from alembic import op

# 🔢 AHORA USAMOS NÚMEROS LIMPIOS Y SECUENCIALES:
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None

roles_table = sa.table(
    "roles",
    sa.column("id", sa.String),
    sa.column("name", sa.String),
    sa.column("description", sa.String),
    sa.column("is_active", sa.Boolean),
    sa.column("created_at", sa.DateTime),
)

def upgrade() -> None:
    now = datetime.now(timezone.utc).isoformat()
    
    vehiculos_role = {
        "id": "a4aeb840-f5ce-4363-ba72-92cf104647c2", 
        "name": "EMPLEADO_VEHICULOS",
        "description": "Empleado vehiculos: vehicles management",
        "is_active": True,
        "created_at": now,
    }

    asignaciones_role = {
        "id": "ff6f1643-dcf0-4e34-af31-0676c0a9e42d", 
        "name": "EMPLEADO_ASIGNACIONES",
        "description": "Empleado asignaciones: assignments management",
        "is_active": True,
        "created_at": now,
    }

    # 🆕 ¡Aquí agregas el rol que habías olvidado!
    reportes_role = {
        "id": "b3bda950-e4dd-4121-cb83-81cf204647d3", 
        "name": "EMPLEADO_REPORTES",
        "description": "Empleado reportes: access to analytics",
        "is_active": True,
        "created_at": now,
    }
    
    # Insertamos los 3 de un solo golpe
    op.bulk_insert(roles_table, [vehiculos_role, asignaciones_role, reportes_role])


def downgrade() -> None:
    op.execute(
        roles_table.delete().where(
            roles_table.c.id.in_([
                "a4aeb840-f5ce-4363-ba72-92cf104647c2",
                "ff6f1643-dcf0-4e34-af31-0676c0a9e42d",
                "b3bda950-e4dd-4121-cb83-81cf204647d3"
            ])
        )
    )