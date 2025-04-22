from collections import defaultdict
from urllib.parse import urlencode

import graphene
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from ....account import events as account_events
from ....account import models as account_models
from ....account.error_codes import AccountErrorCode
from ....account.notifications import send_set_password_notification
from ....account.search import prepare_user_search_document_value
from ....core.exceptions import PermissionDenied
from ....core.tracing import traced_atomic_transaction
from ....core.utils.url import prepare_url, validate_storefront_url
from ...account.i18n import I18nMixin
from ...app.dataloaders import get_app_promise
from ...channel.utils import clean_channel, validate_channel
from ...core import ResolveInfo, SaleorContext
from ...core.descriptions import (
    ADDED_IN_310,
    ADDED_IN_314,
    ADDED_IN_315,
    DEPRECATED_IN_3X_INPUT,
)
from ...core.doc_category import DOC_CATEGORY_USERS
from ...core.enums import LanguageCodeEnum
from ...core.mutations import ModelMutation
from ...core.types import BaseInputObjectType, NonNullList
from ...meta.inputs import MetadataInput
from ...plugins.dataloaders import get_plugin_manager_promise
from ..utils import (
    get_not_manageable_permissions_when_deactivate_or_remove_users,
    get_out_of_scope_users,
)

BILLING_ADDRESS_FIELD = "default_billing_address"
SHIPPING_ADDRESS_FIELD = "default_shipping_address"
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


class UserAddressInput(BaseInputObjectType):
    class Meta:
        doc_category = DOC_CATEGORY_USERS


class CustomerInput(UserInput, UserAddressInput):
    language_code = graphene.Field(
        LanguageCodeEnum, required=False, description="User language code."
    )
    external_reference = graphene.String(
        description="External ID of the customer." + ADDED_IN_310, required=False
    )
    is_confirmed = graphene.Boolean(
        required=False, description="User account is confirmed." + ADDED_IN_315
    )

    class Meta:
        doc_category = DOC_CATEGORY_USERS


class UserCreateInput(CustomerInput):
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


class BaseCustomerCreate(ModelMutation, I18nMixin):
    """Base mutation for customer create used by staff and account."""

    class Arguments:
        input = UserCreateInput(
            description="Fields required to create a customer.", required=True
        )

    class Meta:
        abstract = True

    @classmethod
    def clean_input(cls, info: ResolveInfo, instance, data, **kwargs):
        cleaned_input = super().clean_input(info, instance, data, **kwargs)

        if cleaned_input.get("redirect_url"):
            try:
                validate_storefront_url(cleaned_input.get("redirect_url"))
            except ValidationError as error:
                raise ValidationError(
                    {"redirect_url": error}, code=AccountErrorCode.INVALID.value
                )

        email = cleaned_input.get("email")
        if email:
            cleaned_input["email"] = email.lower()

        # Always set the user as unconfirmed during account creation.
        # The confirmation will take place when the user sets the password.
        if not instance.id:
            cleaned_input["is_confirmed"] = False

        return cleaned_input

    @classmethod
    @traced_atomic_transaction()
    def save(cls, info: ResolveInfo, instance, cleaned_input):
        default_shipping_address = cleaned_input.get(SHIPPING_ADDRESS_FIELD)
        manager = get_plugin_manager_promise(info.context).get()
        if default_shipping_address:
            default_shipping_address = manager.change_user_address(
                default_shipping_address, "shipping", instance
            )
            default_shipping_address.save()
            instance.default_shipping_address = default_shipping_address
        default_billing_address = cleaned_input.get(BILLING_ADDRESS_FIELD)
        if default_billing_address:
            default_billing_address = manager.change_user_address(
                default_billing_address, "billing", instance
            )
            default_billing_address.save()
            instance.default_billing_address = default_billing_address

        is_creation = instance.pk is None

        try:
            with transaction.atomic():
                instance.save()
        except IntegrityError:
            try:
                # Verify if object already exists in DB.
                # If yes, it means we have a race-condition
                # This eventually leads to ValidationError because this user
                # already exists
                account_models.User.objects.get(email=instance.email)

                raise ValidationError(
                    {
                        # This validation error mimics built-in validation error
                        # So graphQL response is the same
                        "email": ValidationError(
                            "User with this Email already exists.",
                            code=AccountErrorCode.UNIQUE.value,
                        )
                    }
                )
            except instance.DoesNotExist:
                pass
            raise

        if default_billing_address:
            instance.addresses.add(default_billing_address)
        if default_shipping_address:
            instance.addresses.add(default_shipping_address)

        instance.search_document = prepare_user_search_document_value(instance)
        instance.save(update_fields=["search_document", "updated_at"])

        # The instance is a new object in db, create an event
        if is_creation:
            cls.call_event(manager.customer_created, instance)
            account_events.customer_account_created_event(user=instance)
        else:
            cls.call_event(manager.customer_updated, instance)

        if redirect_url := cleaned_input.get("redirect_url"):
            channel_slug = cleaned_input.get("channel")
            if not instance.is_staff:
                channel_slug = clean_channel(
                    channel_slug, error_class=AccountErrorCode, allow_replica=False
                ).slug
            elif channel_slug is not None:
                channel_slug = validate_channel(
                    channel_slug, error_class=AccountErrorCode
                ).slug
            send_set_password_notification(
                redirect_url,
                instance,
                manager,
                channel_slug,
            )
            token = default_token_generator.make_token(instance)
            params = urlencode({"email": instance.email, "token": token})
            cls.call_event(
                manager.account_set_password_requested,
                instance,
                channel_slug,
                token,
                prepare_url(params, redirect_url),
            )

    @classmethod
    def post_save_action(cls, info: ResolveInfo, instance, cleaned_input):
        if cleaned_input.get("metadata"):
            manager = get_plugin_manager_promise(info.context).get()
            cls.call_event(manager.customer_metadata_updated, instance)

        if cleaned_input.get("first_name") or cleaned_input.get("last_name"):
            pass


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


class CustomerDeleteMixin(UserDeleteMixin):
    class Meta:
        abstract = True

    @classmethod
    def clean_instance(cls, info: ResolveInfo, instance) -> None:
        super().clean_instance(info, instance)
        if instance.is_staff:
            raise ValidationError(
                {
                    "id": ValidationError(
                        "Cannot delete a staff account.",
                        code=AccountErrorCode.DELETE_STAFF_ACCOUNT.value,
                    )
                }
            )

    @classmethod
    def post_process(cls, info: ResolveInfo, deleted_count=1):
        app = get_app_promise(info.context).get()
        account_events.customer_deleted_event(
            staff_user=info.context.user,
            app=app,
            deleted_count=deleted_count,
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
