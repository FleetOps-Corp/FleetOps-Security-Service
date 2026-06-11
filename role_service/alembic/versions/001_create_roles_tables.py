"""create roles and user_roles tables

Revision ID: 001
Revises:
Create Date: 2026-01-01 00:00:00.000000

SAD Reference: Infrastructure Layer — "Tablas: roles · user_roles" (pág. 5)
"""

from alembic import op
import sqlalchemy as sa

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

    # Seed the four canonical roles (SAD §1)
    import uuid
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    roles = [
        ("EMPLEADO", "Basic employee: access to own assignments"),
        ("EMPLEADO_MANTENIMIENTO", "Maintenance employee: access to vehicle maintenance info"),
        ("EMPLEADO_INCIDENTES", "Incident employee: access to vehicle and driver incident info"),
        ("ADMINISTRADOR", "Administrator: full access for strategic reporting"),
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
        [
            {"id": str(uuid.uuid4()), "name": name, "description": desc,
             "is_active": True, "created_at": now}
            for name, desc in roles
        ],
    )


def downgrade() -> None:
    op.drop_table("user_roles")
    op.drop_table("roles")
