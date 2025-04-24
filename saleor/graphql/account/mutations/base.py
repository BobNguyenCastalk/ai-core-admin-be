from collections import defaultdict

import graphene
from django.core.exceptions import ValidationError

from ....account.error_codes import AccountErrorCode
from ....core.exceptions import PermissionDenied
from ...app.dataloaders import get_app_promise
from ...core import ResolveInfo, SaleorContext
from ...core.descriptions import (
    ADDED_IN_314,
    ADDED_IN_315,
    DEPRECATED_IN_3X_INPUT,
)
from ...core.doc_category import DOC_CATEGORY_USERS
from ...core.types import BaseInputObjectType, NonNullList
from ...meta.inputs import MetadataInput
from ..utils import (
    get_not_manageable_permissions_when_deactivate_or_remove_users,
    get_out_of_scope_users,
)

INVALID_TOKEN = "Invalid or expired token."


class UserInput(BaseInputObjectType):
    first_name = graphene.String(description="Given name.")
    last_name = graphene.String(description="Family name.")
    email = graphene.String(description="The unique email address of the user.")
    is_active = graphene.Boolean(required=False, description="User account is active.")
    note = graphene.String(description="A note about the user.")
    metadata = NonNullList(
        MetadataInput,
        description="Fields required to update the user metadata." + ADDED_IN_314,
        required=False,
    )
    private_metadata = NonNullList(
        MetadataInput,
        description=(
            "Fields required to update the user private metadata." + ADDED_IN_314
        ),
        required=False,
    )

    class Meta:
        doc_category = DOC_CATEGORY_USERS


class UserCreateInput(UserInput):
    redirect_url = graphene.String(
        description=(
            "URL of a view where users should be redirected to "
            "set the password. URL in RFC 1808 format."
        )
    )
    channel = graphene.String(
        description=(
            "Slug of a channel which will be used for notify user. Optional when "
            "only one channel exists."
        )
    )
    is_confirmed = graphene.Boolean(
        required=False,
        description=(
            "User account is confirmed."
            + ADDED_IN_315
            + DEPRECATED_IN_3X_INPUT
            + "\n\nThe user will be always set as unconfirmed. "
            "The confirmation will take place when the user sets the password."
        ),
    )

    class Meta:
        doc_category = DOC_CATEGORY_USERS


class UserDeleteMixin:
    class Meta:
        abstract = True

    @classmethod
    def clean_instance(cls, info: ResolveInfo, instance) -> None:
        user = info.context.user
        if instance == user:
            raise ValidationError(
                {
                    "id": ValidationError(
                        "You cannot delete your own account.",
                        code=AccountErrorCode.DELETE_OWN_ACCOUNT.value,
                    )
                }
            )
        elif instance.is_superuser:
            raise ValidationError(
                {
                    "id": ValidationError(
                        "Cannot delete this account.",
                        code=AccountErrorCode.DELETE_SUPERUSER_ACCOUNT.value,
                    )
                }
            )


class StaffDeleteMixin(UserDeleteMixin):
    class Meta:
        abstract = True

    @classmethod
    def check_permissions(
        cls,
        context: SaleorContext,
        permissions=None,
        require_all_permissions=False,
        **data,
    ):
        if get_app_promise(context).get():
            raise PermissionDenied(
                message="Apps are not allowed to perform this mutation."
            )
        return super().check_permissions(context, permissions)  # type: ignore[misc] # mixin # noqa: E501

    @classmethod
    def clean_instance(cls, info: ResolveInfo, instance):
        errors: defaultdict[str, list[ValidationError]] = defaultdict(list)

        requestor = info.context.user

        cls.check_if_users_can_be_deleted(info, [instance], "id", errors)
        cls.check_if_requestor_can_manage_users(requestor, [instance], "id", errors)
        cls.check_if_removing_left_not_manageable_permissions(
            requestor, [instance], "id", errors
        )
        if errors:
            raise ValidationError(errors)

    @classmethod
    def check_if_users_can_be_deleted(cls, info: ResolveInfo, instances, field, errors):
        """Check if only staff users will be deleted. Cannot delete non-staff users."""
        not_staff_users = set()
        for user in instances:
            if not user.is_staff:
                not_staff_users.add(user)
            try:
                super().clean_instance(info, user)
            except ValidationError as error:
                errors["ids"].append(error)

        if not_staff_users:
            user_pks = [
                graphene.Node.to_global_id("User", user.pk) for user in not_staff_users
            ]
            msg = "Cannot delete a non-staff users."
            code = AccountErrorCode.DELETE_NON_STAFF_USER.value
            params = {"users": user_pks}
            errors[field].append(ValidationError(msg, code=code, params=params))

    @classmethod
    def check_if_requestor_can_manage_users(cls, requestor, instances, field, errors):
        """Requestor can't manage users with wider scope of permissions."""
        if requestor.is_superuser:
            return
        out_of_scope_users = get_out_of_scope_users(requestor, instances)
        if out_of_scope_users:
            user_pks = [
                graphene.Node.to_global_id("User", user.pk)
                for user in out_of_scope_users
            ]
            msg = "You can't manage this users."
            code = AccountErrorCode.OUT_OF_SCOPE_USER.value
            params = {"users": user_pks}
            error = ValidationError(msg, code=code, params=params)
            errors[field] = error

    @classmethod
    def check_if_removing_left_not_manageable_permissions(
        cls, requestor, users, field, errors: defaultdict[str, list[ValidationError]]
    ):
        """Check if after removing users all permissions will be manageable.

        After removing users, for each permission, there should be at least one
        active staff member who can manage it (has both “manage staff” and
        this permission).
        """
        if requestor.is_superuser:
            return
        permissions = get_not_manageable_permissions_when_deactivate_or_remove_users(
            users
        )
        if permissions:
            # add error
            msg = "Users cannot be removed, some of permissions will not be manageable."
            code = AccountErrorCode.LEFT_NOT_MANAGEABLE_PERMISSION.value
            params = {"permissions": permissions}
            error = ValidationError(msg, code=code, params=params)
            errors[field] = [error]
