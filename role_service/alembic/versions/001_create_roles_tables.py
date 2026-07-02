"""create roles and user_roles tables

Revision ID: 001
Revises:
Create Date: 2026-01-01 00:00:00.000000

SAD Reference: Infrastructure Layer — "Tablas: roles · user_roles" (pág. 5)
"""

import sqlalchemy as sa

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # roles — catalog of system roles (SAD §1)
    op.create_table(
        "roles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # user_roles — assignment of roles to users (many-to-many via user_id + role_id)
    op.create_table(
        "user_roles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column(
            "role_id",
            sa.String(36),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("assigned_by", sa.String(36), nullable=True),  # admin user_id
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    # 🆕 Declaramos explícitamente los UUIDs que se mantendrán para siempre
    static_roles = [
        {
            "id": "10131318-c79e-4691-91c3-30cd60056ab7",
            "name": "EMPLEADO",
            "description": "Basic employee: access to own assignments",
            "is_active": True,
            "created_at": now,
        },
        {
            "id": "2024b4f5-1445-4b08-8e81-d41c19b2650c",
            "name": "EMPLEADO_MANTENIMIENTO",
            "description": "Maintenance employee: access to vehicle maintenance info",
            "is_active": True,
            "created_at": now,
        },
        {
            "id": "3034c5a6-2556-4c19-9f92-e52d20c3761d",
            "name": "EMPLEADO_INCIDENTES",
            "description": "Incident employee: access to vehicle and driver incident info",
            "is_active": True,
            "created_at": now,
        },
        {
            "id": "8db0189a-3505-41c2-ae29-45861557be8b",
            "name": "ADMINISTRADOR",
            "description": "Administrator: full access for strategic reporting",
            "is_active": True,
            "created_at": now,
        },
    ]

    op.bulk_insert(
        sa.table(
            "roles",
            sa.column("id", sa.String),
            sa.column("name", sa.String),
            sa.column("description", sa.String),
            sa.column("is_active", sa.Boolean),
            sa.column("created_at", sa.DateTime),
        ),
        static_roles,  # 💥 Insertamos la lista estática limpia
    )


def downgrade() -> None:
    op.drop_table("user_roles")
    op.drop_table("roles")
