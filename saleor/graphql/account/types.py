from typing import cast

import graphene
from django.contrib.auth import get_user_model
from graphene import relay

from ...account import models
from ...core.exceptions import PermissionDenied
from ...permission.auth_filters import AuthorizationFilters
from ...permission.enums import (
    AccountPermissions,
)
from ..channel.types import Channel
from ..core import ResolveInfo
from ..core.connection import CountableConnection
from ..core.context import get_database_connection_name
from ..core.descriptions import (
    ADDED_IN_310,
    ADDED_IN_314,
    ADDED_IN_315,
    DEPRECATED_IN_3X_FIELD,
    PREVIEW_FEATURE,
)
from ..core.doc_category import DOC_CATEGORY_USERS
from ..core.enums import LanguageCodeEnum
from ..core.federation import federated_entity, resolve_federation_references
from ..core.fields import PermissionsField
from ..core.scalars import UUID, DateTime
from ..core.tracing import traced_resolver
from ..core.types import (
    BaseObjectType,
    ModelObjectType,
    NonNullList,
    Permission,
)
from ..core.utils import from_global_id_or_error, str_to_enum
from ..meta.types import ObjectWithMetadata
from ..utils import format_permissions_for_display, get_user_or_app_from_context
from .dataloaders import (
    AccessibleChannelsByGroupIdLoader,
    AccessibleChannelsByUserIdLoader,
    RestrictedChannelAccessByUserIdLoader,
)
from .utils import can_user_manage_group, get_groups_which_user_can_manage


class UserPermission(Permission):
    source_permission_groups = NonNullList(
        "saleor.graphql.account.types.Group",
        description="List of user permission groups which contains this permission.",
        user_id=graphene.Argument(
            graphene.ID,
            description="ID of user whose groups should be returned.",
            required=True,
        ),
        required=False,
    )

    class Meta:
        description = "Represents user's permissions."
        doc_category = DOC_CATEGORY_USERS

    @staticmethod
    @traced_resolver
    def resolve_source_permission_groups(root: Permission, info: ResolveInfo, user_id):
        _type, user_id = from_global_id_or_error(user_id, only_type="User")
        groups = models.Group.objects.using(
            get_database_connection_name(info.context)
        ).filter(user__pk=user_id, permissions__name=root.name)
        return groups


@federated_entity("id")
@federated_entity("email")
class User(ModelObjectType[models.User]):
    id = graphene.GlobalID(required=True, description="The ID of the user.")
    email = graphene.String(required=True, description="The email address of the user.")
    first_name = graphene.String(
        required=True, description="The given name of the address."
    )
    last_name = graphene.String(
        required=True, description="The family name of the address."
    )
    is_staff = graphene.Boolean(
        required=True, description="Determine if the user is a staff admin."
    )
    is_active = graphene.Boolean(
        required=True, description="Determine if the user is active."
    )
    is_confirmed = graphene.Boolean(
        required=True,
        description="Determines if user has confirmed email." + ADDED_IN_315,
    )
    checkout_tokens = NonNullList(
        UUID,
        description="Returns the checkout UUID's assigned to this user.",
        channel=graphene.String(
            description="Slug of a channel for which the data should be returned."
        ),
        deprecation_reason=(f"{DEPRECATED_IN_3X_FIELD} Use `checkoutIds` instead."),
    )
    checkout_ids = NonNullList(
        graphene.ID,
        description="Returns the checkout ID's assigned to this user.",
        channel=graphene.String(
            description="Slug of a channel for which the data should be returned."
        ),
    )
    note = PermissionsField(
        graphene.String,
        description="A note about the customer.",
        permissions=[AccountPermissions.MANAGE_USERS, AccountPermissions.MANAGE_STAFF],
    )
    user_permissions = NonNullList(
        UserPermission, description="List of user's permissions."
    )
    permission_groups = NonNullList(
        "saleor.graphql.account.types.Group",
        description="List of user's permission groups.",
    )
    editable_groups = NonNullList(
        "saleor.graphql.account.types.Group",
        description="List of user's permission groups which user can manage.",
    )
    accessible_channels = NonNullList(
        Channel,
        description=(
            "List of channels the user has access to. The sum of channels from all "
            "user groups. If at least one group has `restrictedAccessToChannels` "
            "set to False - all channels are returned." + ADDED_IN_314 + PREVIEW_FEATURE
        ),
    )
    restricted_access_to_channels = graphene.Boolean(
        required=True,
        description=(
            "Determine if user have restricted access to channels. False if at least "
            "one user group has `restrictedAccessToChannels` set to False."
        )
        + ADDED_IN_314
        + PREVIEW_FEATURE,
    )
    language_code = graphene.Field(
        LanguageCodeEnum, description="User language code.", required=True
    )
    external_reference = graphene.String(
        description=f"External ID of this user. {ADDED_IN_310}", required=False
    )

    last_login = DateTime(
        description="The date when the user last time log in to the system."
    )
    date_joined = DateTime(
        required=True, description="The data when the user create account."
    )
    updated_at = DateTime(
        required=True,
        description="The data when the user last update the account information.",
    )

    class Meta:
        description = "Represents user data."
        interfaces = [relay.Node, ObjectWithMetadata]
        model = get_user_model()
        doc_category = DOC_CATEGORY_USERS

    @staticmethod
    def resolve_addresses(root: models.User, _info: ResolveInfo):
        return root.addresses.annotate_default(root).all()

    @staticmethod
    def resolve_user_permissions(root: models.User, info: ResolveInfo):
        from .resolvers import resolve_permissions

        return resolve_permissions(root, info)

    @staticmethod
    def resolve_permission_groups(root: models.User, info: ResolveInfo):
        return root.groups.using(get_database_connection_name(info.context)).all()

    @staticmethod
    def resolve_editable_groups(root: models.User, info: ResolveInfo):
        database_connection_name = get_database_connection_name(info.context)
        return get_groups_which_user_can_manage(root, database_connection_name)

    @staticmethod
    def resolve_accessible_channels(root: models.Group, info: ResolveInfo):
        # Sum of channels from all user groups. If at least one group has
        # `restrictedAccessToChannels` set to False - all channels are returned
        return AccessibleChannelsByUserIdLoader(info.context).load(root.id)

    @staticmethod
    def resolve_restricted_access_to_channels(root: models.Group, info: ResolveInfo):
        # Returns False if at least one user group has `restrictedAccessToChannels`
        # set to False
        return RestrictedChannelAccessByUserIdLoader(info.context).load(root.id)

    @staticmethod
    def resolve_note(root: models.User, _info: ResolveInfo):
        return root.note

    @staticmethod
    def resolve_language_code(root, _info: ResolveInfo):
        return LanguageCodeEnum[str_to_enum(root.language_code)]


class UserCountableConnection(CountableConnection):
    class Meta:
        doc_category = DOC_CATEGORY_USERS
        node = User


class ChoiceValue(graphene.ObjectType):
    raw = graphene.String(description="The raw name of the choice.")
    verbose = graphene.String(description="The verbose name of the choice.")


FORMAT_FILED_DESCRIPTION = (
    "\n\nMany fields in the JSON refer to address fields by one-letter "
    "abbreviations. These are defined as follows:\n\n"
    "- `N`: Name\n"
    "- `O`: Organization\n"
    "- `A`: Street Address Line(s)\n"
    "- `D`: Dependent locality (may be an inner-city district or a suburb)\n"
    "- `C`: City or Locality\n"
    "- `S`: Administrative area such as a state, province, island etc\n"
    "- `Z`: Zip or postal code\n"
    "- `X`: Sorting code\n\n"
    "[Click here for more information.](https://github.com/google/libaddressinput/wiki/AddressValidationMetadata)"
)


@federated_entity("id")
class Group(ModelObjectType[models.Group]):
    id = graphene.GlobalID(required=True, description="The ID of the group.")
    name = graphene.String(required=True, description="The name of the group.")
    users = PermissionsField(
        NonNullList(User),
        description="List of group users",
        permissions=[
            AccountPermissions.MANAGE_STAFF,
        ],
    )
    permissions = NonNullList(Permission, description="List of group permissions")
    user_can_manage = graphene.Boolean(
        required=True,
        description=(
            "True, if the currently authenticated user has rights to manage a group."
        ),
    )
    accessible_channels = NonNullList(
        Channel,
        description="List of channels the group has access to."
        + ADDED_IN_314
        + PREVIEW_FEATURE,
    )
    restricted_access_to_channels = graphene.Boolean(
        required=True,
        description="Determine if the group have restricted access to channels."
        + ADDED_IN_314
        + PREVIEW_FEATURE,
    )

    class Meta:
        description = "Represents permission group data."
        interfaces = [relay.Node]
        model = models.Group
        doc_category = DOC_CATEGORY_USERS

    @staticmethod
    def resolve_users(root: models.Group, info: ResolveInfo):
        database_connection_name = get_database_connection_name(info.context)
        return root.user_set.using(database_connection_name).all()  # type: ignore[attr-defined]

    @staticmethod
    def resolve_permissions(root: models.Group, info: ResolveInfo):
        database_connection_name = get_database_connection_name(info.context)
        permissions = (
            root.permissions.using(database_connection_name)
            .prefetch_related("content_type")
            .order_by("codename")
        )
        return format_permissions_for_display(permissions)

    @staticmethod
    def resolve_user_can_manage(root: models.Group, info: ResolveInfo) -> bool:
        user = info.context.user
        if not user:
            return False
        return can_user_manage_group(info, user, root)

    @staticmethod
    def resolve_accessible_channels(root: models.Group, info: ResolveInfo):
        return AccessibleChannelsByGroupIdLoader(info.context).load(root.id)

    @staticmethod
    def __resolve_references(roots: list["Group"], info: ResolveInfo):
        from .resolvers import resolve_permission_groups

        requestor = get_user_or_app_from_context(info.context)
        if not requestor or not requestor.has_perm(AccountPermissions.MANAGE_STAFF):
            qs = models.Group.objects.none()
        else:
            qs = resolve_permission_groups(info)

        return resolve_federation_references(Group, roots, qs)


class GroupCountableConnection(CountableConnection):
    class Meta:
        doc_category = DOC_CATEGORY_USERS
        node = Group
