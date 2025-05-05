from django.db.models import Q

from ...account import models
from ...core.exceptions import PermissionDenied
from ...graphql.core.context import get_database_connection_name
from ...permission.enums import AccountPermissions
from ...permission.utils import has_one_of_permissions
from ..core import ResolveInfo
from ..core.tracing import traced_resolver
from ..core.utils import from_global_id_or_error
from ..utils import format_permissions_for_display, get_user_or_app_from_context
from .types import User
from .utils import (
    get_user_permissions,
)

USER_SEARCH_FIELDS = (
    "email",
    "first_name",
    "last_name",
)


def resolve_customers(info):
    return models.User.objects.customers().using(
        get_database_connection_name(info.context)
    )


def resolve_permission_group(info, id):
    return (
        models.Group.objects.using(get_database_connection_name(info.context))
        .filter(id=id)
        .first()
    )


def resolve_permission_groups(info):
    return models.Group.objects.using(get_database_connection_name(info.context)).all()


def resolve_staff_users(info):
    return models.User.objects.staff().using(get_database_connection_name(info.context))


@traced_resolver
def resolve_user(info, id=None, email=None, external_reference=None):
    requester = get_user_or_app_from_context(info.context)
    if requester:
        connection_name = get_database_connection_name(info.context)
        filter_kwargs = {}
        if id:
            _model, filter_kwargs["pk"] = from_global_id_or_error(id, User)
        if email:
            filter_kwargs["email"] = email
        if external_reference:
            filter_kwargs["external_reference"] = external_reference
        if requester.has_perms(
            [AccountPermissions.MANAGE_STAFF, AccountPermissions.MANAGE_USERS]
        ):
            return (
                models.User.objects.using(connection_name)
                .filter(**filter_kwargs)
                .first()
            )
        if requester.has_perm(AccountPermissions.MANAGE_STAFF):
            return (
                models.User.objects.staff()
                .using(connection_name)
                .filter(**filter_kwargs)
                .first()
            )
        if has_one_of_permissions(
            requester, [AccountPermissions.MANAGE_USERS]
        ):
            return (
                models.User.objects.customers()
                .using(connection_name)
                .filter(**filter_kwargs)
                .first()
            )
    return PermissionDenied(
        permissions=[
            AccountPermissions.MANAGE_STAFF,
            AccountPermissions.MANAGE_USERS,
        ]
    )


@traced_resolver
def resolve_users(info, ids=None, emails=None):
    requester = get_user_or_app_from_context(info.context)
    connection_name = get_database_connection_name(info.context)
    if not requester:
        return models.User.objects.none()

    if requester.has_perms(
        [AccountPermissions.MANAGE_STAFF, AccountPermissions.MANAGE_USERS]
    ):
        qs = models.User.objects.using(connection_name).all()
    elif requester.has_perm(AccountPermissions.MANAGE_STAFF):
        qs = models.User.objects.staff().using(connection_name)
    elif requester.has_perm(AccountPermissions.MANAGE_USERS):
        qs = models.User.objects.customers().using(connection_name)
    elif requester.id:
        # If user has no access to all users, we can only return themselves, but
        # only if they are authenticated and one of requested users
        qs = models.User.objects.using(connection_name).filter(id=requester.id)
    else:
        qs = models.User.objects.none()

    if ids:
        ids = {from_global_id_or_error(id, User, raise_error=True)[1] for id in ids}

    if ids and emails:
        return qs.filter(Q(id__in=ids) | Q(email__in=emails))
    elif ids:
        return qs.filter(id__in=ids)
    return qs.filter(email__in=emails)


def resolve_permissions(root: models.User, info: ResolveInfo):
    database_connection_name = get_database_connection_name(info.context)
    permissions = get_user_permissions(root).using(database_connection_name)
    permissions = permissions.order_by("codename")
    return format_permissions_for_display(permissions)
