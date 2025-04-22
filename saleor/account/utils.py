
from django.db.models import Exists, OuterRef

from ..core.utils.events import call_event
from ..permission.models import Permission
from ..plugins.manager import get_plugins_manager
from .models import Group, User


def create_superuser(credentials):
    user, created = User.objects.get_or_create(
        email=credentials["email"],
        defaults={"is_active": True, "is_staff": True, "is_superuser": True},
    )
    if created:
        user.set_password(credentials["password"])
        user.save()
        msg = f"Superuser - {credentials['email']}/{credentials['password']}"
    else:
        msg = f"Superuser already exists - {credentials['email']}"
    return msg


def remove_staff_member(staff):
    """Remove staff member account only if it has no orders placed.

    Otherwise, switches is_staff status to False.
    """
    if staff.orders.exists():
        staff.is_staff = False
        staff.user_permissions.clear()
        staff.save()
    else:
        staff.delete()


def retrieve_user_by_email(email):
    """Retrieve user by email.

    Email lookup is case-insensitive, unless the query returns more than one user. In
    such a case, function return case-sensitive result.
    """
    users = list(User.objects.filter(email__iexact=email))

    if len(users) > 1:
        users_exact = [user for user in users if user.email == email]
        users_iexact = [user for user in users if user.email == email.lower()]
        users = users_exact or users_iexact

    if users:
        return users[0]
    return None


def get_user_groups_permissions(user: User):
    GroupUser = User.groups.through
    group_users = GroupUser._default_manager.filter(user_id=user.id).values("group_id")
    GroupPermissions = Group.permissions.through
    group_permissions = GroupPermissions.objects.filter(
        Exists(group_users.filter(group_id=OuterRef("group_id")))
    ).values("permission_id")
    return Permission.objects.filter(
        Exists(group_permissions.filter(permission_id=OuterRef("id")))
    )


def send_user_event(user: User, created: bool, updated: bool):
    """Send created or updated event for user."""
    manager = get_plugins_manager(allow_replica=False)
    event = None
    if created:
        event = manager.staff_created if user.is_staff else manager.customer_created
    elif updated:
        event = manager.staff_updated if user.is_staff else manager.customer_updated
    if event:
        call_event(event, user)
