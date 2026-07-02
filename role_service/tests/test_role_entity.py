"""
Unit Tests — Role and UserRoleAssignment Entities (Domain Layer)
=================================================================
Coverage target: 100% of Role and UserRoleAssignment public methods.
Pattern: AAA (Arrange → Act → Assert)
"""

from datetime import datetime

from app.domain.role import Role, RoleName, UserRoleAssignment


class TestRoleName:
    def test_all_four_roles_exist(self):
        names = {r.value for r in RoleName}
        assert names == {
            "EMPLEADO",
            "EMPLEADO_MANTENIMIENTO",
            "EMPLEADO_INCIDENTES",
            "ADMINISTRADOR",
        }

    def test_role_name_is_string(self):
        assert isinstance(RoleName.EMPLEADO, str)


class TestRole:
    def test_create_generates_uuid_id(self):
        role = Role.create("EMPLEADO", "Basic employee")
        assert len(role.id) == 36

    def test_create_normalizes_name_to_uppercase(self):
        role = Role.create("  empleado  ", "desc")
        assert role.name == "EMPLEADO"

    def test_create_sets_is_active_true(self):
        role = Role.create("EMPLEADO")
        assert role.is_active is True

    def test_create_sets_created_at(self):
        role = Role.create("EMPLEADO")
        assert role.created_at is not None

    def test_create_two_roles_have_different_ids(self):
        r1 = Role.create("EMPLEADO")
        r2 = Role.create("EMPLEADO")
        assert r1.id != r2.id

    def test_deactivate_sets_is_active_false(self):
        role = Role.create("EMPLEADO")
        role.deactivate()
        assert role.is_active is False

    def test_activate_sets_is_active_true_after_deactivation(self):
        role = Role.create("EMPLEADO")
        role.deactivate()
        role.activate()
        assert role.is_active is True

    def test_create_with_empty_description(self):
        role = Role.create("ADMINISTRADOR")
        assert role.description == ""


class TestUserRoleAssignment:
    def test_create_generates_uuid_id(self):
        assignment = UserRoleAssignment.create(user_id="u-1", role_id="r-1", role_name="EMPLEADO")
        assert len(assignment.id) == 36

    def test_create_stores_all_fields(self):
        assignment = UserRoleAssignment.create(
            user_id="u-1",
            role_id="r-2",
            role_name="ADMINISTRADOR",
            assigned_by="admin-99",
        )
        assert assignment.user_id == "u-1"
        assert assignment.role_id == "r-2"
        assert assignment.role_name == "ADMINISTRADOR"
        assert assignment.assigned_by == "admin-99"

    def test_create_with_no_assigned_by_defaults_to_none(self):
        assignment = UserRoleAssignment.create(user_id="u-1", role_id="r-1", role_name="EMPLEADO")
        assert assignment.assigned_by is None

    def test_create_sets_assigned_at_timestamp(self):
        assignment = UserRoleAssignment.create(user_id="u-1", role_id="r-1", role_name="EMPLEADO")
        assert assignment.assigned_at is not None
        assert isinstance(assignment.assigned_at, datetime)
