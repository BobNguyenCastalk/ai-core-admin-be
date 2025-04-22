import graphene
from django.conf import settings
from graphene import AbstractType, Union
from rx import Observable

from ... import __version__
from ...account.models import User
from ...channel.models import Channel
from ...menu.models import MenuItemTranslation
from ...page.models import PageTranslation
from ...webhook.const import MAX_FILTERABLE_CHANNEL_SLUGS_LIMIT
from ...webhook.event_types import WebhookEventAsyncType, WebhookEventSyncType
from ..account.types import User as UserType
from ..app.types import App as AppType
from ..channel import ChannelContext
from ..channel.enums import TransactionFlowStrategyEnum
from ..core import ResolveInfo
from ..core.context import get_database_connection_name
from ..core.descriptions import (
    ADDED_IN_32,
    ADDED_IN_34,
    ADDED_IN_35,
    ADDED_IN_36,
    ADDED_IN_37,
    ADDED_IN_38,
    ADDED_IN_313,
    ADDED_IN_315,
    PREVIEW_FEATURE,
)
from ..core.doc_category import (
    DOC_CATEGORY_MISC,
    DOC_CATEGORY_PAYMENTS,
    DOC_CATEGORY_TAXES,
    DOC_CATEGORY_USERS,
)
from ..core.scalars import JSON, DateTime, PositiveDecimal
from ..core.types import NonNullList, SubscriptionObjectType
from ..translations import types as translation_types

TRANSLATIONS_TYPES_MAP = {
    PageTranslation: translation_types.PageTranslation,
    MenuItemTranslation: translation_types.MenuItemTranslation,
}


class IssuingPrincipal(Union):
    class Meta:
        types = (AppType, UserType)

    @classmethod
    def resolve_type(cls, instance, info: ResolveInfo):
        if isinstance(instance, User):
            return UserType
        return AppType


class Event(graphene.Interface):
    issued_at = DateTime(description="Time of the event.")
    version = graphene.String(description="Saleor version that triggered the event.")
    issuing_principal = graphene.Field(
        IssuingPrincipal,
        description="The user or application that triggered the event.",
    )
    recipient = graphene.Field(
        "saleor.graphql.app.types.App",
        description="The application receiving the webhook.",
    )

    @classmethod
    def get_type(cls, object_type: str):
        return WEBHOOK_TYPES_MAP.get(object_type)

    @classmethod
    def resolve_type(cls, instance, info: ResolveInfo):
        type_str, _ = instance
        return cls.get_type(type_str)

    @staticmethod
    def resolve_issued_at(_root, info: ResolveInfo):
        return info.context.request_time

    @staticmethod
    def resolve_version(_root, _info: ResolveInfo):
        return __version__

    @staticmethod
    def resolve_recipient(_root, info: ResolveInfo):
        return info.context.app

    @staticmethod
    def resolve_issuing_principal(_root, info: ResolveInfo):
        if not info.context.requestor:
            return None
        return info.context.requestor


class AccountOperationBase(AbstractType):
    redirect_url = graphene.String(
        description="The URL to redirect the user after he accepts the request.",
        required=False,
    )
    user = graphene.Field(
        UserType,
        description="The user the event relates to.",
    )
    channel = graphene.Field(
        "saleor.graphql.channel.types.Channel",
        description="The channel data.",
    )
    token = graphene.String(description="The token required to confirm request.")

    @staticmethod
    def resolve_user(root, _info: ResolveInfo):
        _, data = root
        return data["user"]

    @staticmethod
    def resolve_redirect_url(root, _info: ResolveInfo):
        _, data = root
        return data.get("redirect_url")

    @staticmethod
    def resolve_channel(root, info: ResolveInfo):
        _, data = root
        return Channel.objects.using(get_database_connection_name(info.context)).get(
            slug=data["channel_slug"]
        )

    @staticmethod
    def resolve_token(root, _info: ResolveInfo):
        _, data = root
        return data["token"]

    @staticmethod
    def resolve_shop(root, _info: ResolveInfo):
        return Shop()


class AccountConfirmed(SubscriptionObjectType, AccountOperationBase):
    class Meta:
        root_type = None
        enable_dry_run = False
        interfaces = (Event,)
        description = "Event sent when account is confirmed." + ADDED_IN_315
        doc_category = DOC_CATEGORY_USERS


class AccountConfirmationRequested(SubscriptionObjectType, AccountOperationBase):
    class Meta:
        root_type = None
        enable_dry_run = False
        interfaces = (Event,)
        description = (
            "Event sent when account confirmation requested. This event is always sent."
            " enableAccountConfirmationByEmail flag set to True is not required."
            + ADDED_IN_315
        )
        doc_category = DOC_CATEGORY_USERS


class AccountChangeEmailRequested(SubscriptionObjectType, AccountOperationBase):
    new_email = graphene.String(
        description="The new email address the user wants to change to.",
    )

    class Meta:
        root_type = None
        enable_dry_run = False
        interfaces = (Event,)
        description = (
            "Event sent when account change email is requested." + ADDED_IN_315
        )
        doc_category = DOC_CATEGORY_USERS

    @staticmethod
    def resolve_new_email(root, _info: ResolveInfo):
        _, data = root
        return data["new_email"]


class AccountEmailChanged(SubscriptionObjectType, AccountOperationBase):
    new_email = graphene.String(
        description="The new email address.",
    )

    class Meta:
        root_type = None
        enable_dry_run = False
        interfaces = (Event,)
        description = "Event sent when account email is changed." + ADDED_IN_315
        doc_category = DOC_CATEGORY_USERS


class AccountSetPasswordRequested(SubscriptionObjectType, AccountOperationBase):
    class Meta:
        root_type = None
        enable_dry_run = False
        interfaces = (Event,)
        description = (
            "Event sent when setting a new password is requested." + ADDED_IN_315
        )
        doc_category = DOC_CATEGORY_USERS


class AccountDeleteRequested(SubscriptionObjectType, AccountOperationBase):
    class Meta:
        root_type = None
        enable_dry_run = False
        interfaces = (Event,)
        description = "Event sent when account delete is requested." + ADDED_IN_315
        doc_category = DOC_CATEGORY_USERS


class AccountDeleted(SubscriptionObjectType, AccountOperationBase):
    class Meta:
        root_type = None
        enable_dry_run = False
        interfaces = (Event,)
        description = "Event sent when account is deleted." + ADDED_IN_315
        doc_category = DOC_CATEGORY_USERS


class AddressBase(AbstractType):
    address = graphene.Field(
        "saleor.graphql.account.types.Address",
        description="The address the event relates to.",
    )

    @staticmethod
    def resolve_address(root, _info: ResolveInfo):
        _, address = root
        return address


class AddressCreated(SubscriptionObjectType, AddressBase):
    class Meta:
        root_type = "Address"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when new address is created." + ADDED_IN_35


class AddressUpdated(SubscriptionObjectType, AddressBase):
    class Meta:
        root_type = "Address"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when address is updated." + ADDED_IN_35


class AddressDeleted(SubscriptionObjectType, AddressBase):
    class Meta:
        root_type = "Address"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when address is deleted." + ADDED_IN_35


class AppBase(AbstractType):
    app = graphene.Field(
        "saleor.graphql.app.types.App",
        description="The application the event relates to.",
    )

    @staticmethod
    def resolve_app(root, _info: ResolveInfo):
        _, app = root
        return app


class AppInstalled(SubscriptionObjectType, AppBase):
    class Meta:
        root_type = "App"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when new app is installed." + ADDED_IN_34


class AppUpdated(SubscriptionObjectType, AppBase):
    class Meta:
        root_type = "App"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when app is updated." + ADDED_IN_34


class AppDeleted(SubscriptionObjectType, AppBase):
    class Meta:
        root_type = "App"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when app is deleted." + ADDED_IN_34


class AppStatusChanged(SubscriptionObjectType, AppBase):
    class Meta:
        root_type = "App"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when app status has changed." + ADDED_IN_34


class ChannelBase(AbstractType):
    channel = graphene.Field(
        "saleor.graphql.channel.types.Channel",
        description="The channel the event relates to.",
    )

    @staticmethod
    def resolve_channel(root, info: ResolveInfo):
        _, channel = root
        return channel


class ChannelCreated(SubscriptionObjectType, ChannelBase):
    class Meta:
        root_type = "Channel"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when new channel is created." + ADDED_IN_32


class ChannelUpdated(SubscriptionObjectType, ChannelBase):
    class Meta:
        root_type = "Channel"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when channel is updated." + ADDED_IN_32


class ChannelDeleted(SubscriptionObjectType, ChannelBase):
    class Meta:
        root_type = "Channel"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when channel is deleted." + ADDED_IN_32


class ChannelStatusChanged(SubscriptionObjectType, ChannelBase):
    class Meta:
        root_type = "Channel"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when channel status has changed." + ADDED_IN_32


class ChannelMetadataUpdated(SubscriptionObjectType, ChannelBase):
    class Meta:
        root_type = "Channel"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when channel metadata is updated." + ADDED_IN_315


class MenuBase(AbstractType):
    menu = graphene.Field(
        "saleor.graphql.menu.types.Menu",
        channel=graphene.String(
            description="Slug of a channel for which the data should be returned."
        ),
        description="The menu the event relates to.",
    )

    @staticmethod
    def resolve_menu(root, info: ResolveInfo, channel=None):
        _, menu = root
        return ChannelContext(node=menu, channel_slug=channel)


class MenuCreated(SubscriptionObjectType, MenuBase):
    class Meta:
        root_type = "Menu"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when new menu is created." + ADDED_IN_34


class MenuUpdated(SubscriptionObjectType, MenuBase):
    class Meta:
        root_type = "Menu"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when menu is updated." + ADDED_IN_34


class MenuDeleted(SubscriptionObjectType, MenuBase):
    class Meta:
        root_type = "Menu"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when menu is deleted." + ADDED_IN_34


class MenuItemBase(AbstractType):
    menu_item = graphene.Field(
        "saleor.graphql.menu.types.MenuItem",
        channel=graphene.String(
            description="Slug of a channel for which the data should be returned."
        ),
        description="The menu item the event relates to.",
    )

    @staticmethod
    def resolve_menu_item(root, info: ResolveInfo, channel=None):
        _, menu_item = root
        return ChannelContext(node=menu_item, channel_slug=channel)


class MenuItemCreated(SubscriptionObjectType, MenuItemBase):
    class Meta:
        root_type = "MenuItem"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when new menu item is created." + ADDED_IN_34


class MenuItemUpdated(SubscriptionObjectType, MenuItemBase):
    class Meta:
        root_type = "MenuItem"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when menu item is updated." + ADDED_IN_34


class MenuItemDeleted(SubscriptionObjectType, MenuItemBase):
    class Meta:
        root_type = "MenuItem"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when menu item is deleted." + ADDED_IN_34


class UserBase(AbstractType):
    user = graphene.Field(
        "saleor.graphql.account.types.User",
        description="The user the event relates to.",
    )

    @staticmethod
    def resolve_user(root, _info: ResolveInfo):
        _, user = root
        return user


class CustomerCreated(SubscriptionObjectType, UserBase):
    class Meta:
        root_type = "User"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when new customer user is created." + ADDED_IN_32


class CustomerUpdated(SubscriptionObjectType, UserBase):
    class Meta:
        root_type = "User"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when customer user is updated." + ADDED_IN_32


class CustomerMetadataUpdated(SubscriptionObjectType, UserBase):
    class Meta:
        root_type = "User"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when customer user metadata is updated." + ADDED_IN_38


class PermissionGroupBase(AbstractType):
    permission_group = graphene.Field(
        "saleor.graphql.account.types.Group",
        description="The permission group the event relates to.",
    )

    @staticmethod
    def resolve_permission_group(root, _info: ResolveInfo):
        _, permission_group = root
        return permission_group


class PermissionGroupCreated(SubscriptionObjectType, PermissionGroupBase):
    class Meta:
        root_type = "Group"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when new permission group is created." + ADDED_IN_36


class PermissionGroupUpdated(SubscriptionObjectType, PermissionGroupBase):
    class Meta:
        root_type = "Group"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when permission group is updated." + ADDED_IN_36


class PermissionGroupDeleted(SubscriptionObjectType, PermissionGroupBase):
    class Meta:
        root_type = "Group"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when permission group is deleted." + ADDED_IN_36

class StaffCreated(SubscriptionObjectType, UserBase):
    class Meta:
        root_type = "User"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when new staff user is created." + ADDED_IN_35


class StaffUpdated(SubscriptionObjectType, UserBase):
    class Meta:
        root_type = "User"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when staff user is updated." + ADDED_IN_35


class StaffDeleted(SubscriptionObjectType, UserBase):
    class Meta:
        root_type = "User"
        enable_dry_run = True
        interfaces = (Event,)
        description = "Event sent when staff user is deleted." + ADDED_IN_35


class StaffSetPasswordRequested(SubscriptionObjectType, AccountOperationBase):
    class Meta:
        root_type = None
        enable_dry_run = False
        interfaces = (Event,)
        description = (
            "Event sent when setting a new password for staff is requested."
            + ADDED_IN_315
        )
        doc_category = DOC_CATEGORY_USERS


class PaymentGatewayInitializeSession(SubscriptionObjectType):
    data = graphene.Field(
        JSON,
        description="Payment gateway data in JSON format, received from storefront.",
    )
    amount = graphene.Field(
        PositiveDecimal,
        description="Amount requested for initializing the payment gateway.",
    )

    class Meta:
        interfaces = (Event,)
        root_type = None
        enable_dry_run = False
        description = (
            "Event sent when user wants to initialize the payment gateway."
            + ADDED_IN_313
            + PREVIEW_FEATURE
        )
        doc_category = DOC_CATEGORY_PAYMENTS

    @staticmethod
    def resolve_source_object(root, _info: ResolveInfo):
        _, objects = root
        source_object, _, _ = objects
        return source_object

    @staticmethod
    def resolve_data(root, _info: ResolveInfo):
        _, objects = root
        _, data, _ = objects
        return data

    @staticmethod
    def resolve_amount(root, _info: ResolveInfo):
        _, objects = root
        _, _, amount = objects
        return amount


class TransactionProcessAction(SubscriptionObjectType, AbstractType):
    amount = PositiveDecimal(
        description="Transaction amount to process.", required=True
    )
    currency = graphene.String(description="Currency of the amount.", required=True)
    action_type = graphene.Field(TransactionFlowStrategyEnum, required=True)

    class Meta:
        doc_category = DOC_CATEGORY_PAYMENTS


class TransactionItemMetadataUpdated(SubscriptionObjectType):

    class Meta:
        root_type = "TransactionItem"
        enable_dry_run = True
        interfaces = (Event,)
        description = (
            "Event sent when transaction item metadata is updated." + ADDED_IN_38
        )
        doc_category = DOC_CATEGORY_PAYMENTS

    @staticmethod
    def resolve_transaction(root, _info: ResolveInfo):
        _, transaction_item = root
        return transaction_item


class CalculateTaxes(SubscriptionObjectType):
    tax_base = graphene.Field(
        "saleor.graphql.core.types.taxes.TaxableObject", required=True
    )

    class Meta:
        root_type = None
        enable_dry_run = False
        interfaces = (Event,)
        description = (
            "Synchronous webhook for calculating checkout/order taxes." + ADDED_IN_37
        )
        doc_category = DOC_CATEGORY_TAXES

    @staticmethod
    def resolve_tax_base(root, _info: ResolveInfo):
        _, tax_base = root
        return tax_base


def default_order_resolver(root, info, channels=None):
    return Observable.from_([root])


channels_argument = graphene.Argument(
    NonNullList(graphene.String),
    description=(
        "List of channel slugs. The event will be sent only if the order "
        "belongs to one of the provided channels. If the channel slug list is "
        "empty, orders that belong to any channel will be sent. Maximally "
        f"{MAX_FILTERABLE_CHANNEL_SLUGS_LIMIT} items."
    ),
)


class Subscription(SubscriptionObjectType):
    event = graphene.Field(
        Event,
        description="Look up subscription event." + ADDED_IN_32,
    )
    class Meta:
        doc_category = DOC_CATEGORY_MISC

    @staticmethod
    def resolve_event(root, info: ResolveInfo):
        return Observable.from_([root])

    @staticmethod
    def resolve_order_bulk_created(root, info: ResolveInfo, channels=None):
        event_type, orders = root
        if event_type != WebhookEventAsyncType.ORDER_BULK_CREATED:
            return Observable.from_([])

        orders_to_return = []
        if channels:
            channel_ids = (
                Channel.objects.using(settings.DATABASE_CONNECTION_REPLICA_NAME)
                .filter(slug__in=channels)
                .values_list("id", flat=True)
            )
            for order in orders:
                if order.channel_id in channel_ids:
                    orders_to_return.append(order)
            root = (event_type, orders_to_return)
            return Observable.from_([root])
        return Observable.from_([root])


class ThumbnailCreated(SubscriptionObjectType):
    id = graphene.ID(description="Thumbnail id.")
    url = graphene.String(description="Thumbnail url.")
    object_id = graphene.ID(
        description="Object the thumbnail refers to."
    )
    media_url = graphene.String(description="Original media url.")

    class Meta:
        root_type = None
        enable_dry_run = False
        interfaces = (Event,)
        description = "Event sent when thumbnail is created."
        doc_category = DOC_CATEGORY_MISC

    @staticmethod
    def resolve_id(root, info: ResolveInfo):
        _, thumbnail = root
        return graphene.Node.to_global_id("Thumbnail", thumbnail.id)

    @staticmethod
    def resolve_url(root, info: ResolveInfo):
        _, thumbnail = root
        return thumbnail.image.url

    @staticmethod
    def resolve_object_id(root, info: ResolveInfo):
        _, thumbnail = root
        type = thumbnail.instance.__class__.__name__
        return graphene.Node.to_global_id(type, thumbnail.instance.id)


SYNC_WEBHOOK_TYPES_MAP = {
    WebhookEventSyncType.CHECKOUT_CALCULATE_TAXES: CalculateTaxes,
    WebhookEventSyncType.ORDER_CALCULATE_TAXES: CalculateTaxes,
    WebhookEventSyncType.PAYMENT_GATEWAY_INITIALIZE_SESSION: (
        PaymentGatewayInitializeSession
    ),
}


ASYNC_WEBHOOK_TYPES_MAP = {
    WebhookEventAsyncType.ACCOUNT_CONFIRMATION_REQUESTED: AccountConfirmationRequested,
    WebhookEventAsyncType.ACCOUNT_CHANGE_EMAIL_REQUESTED: AccountChangeEmailRequested,
    WebhookEventAsyncType.ACCOUNT_EMAIL_CHANGED: AccountEmailChanged,
    WebhookEventAsyncType.ACCOUNT_SET_PASSWORD_REQUESTED: AccountSetPasswordRequested,
    WebhookEventAsyncType.ACCOUNT_CONFIRMED: AccountConfirmed,
    WebhookEventAsyncType.ACCOUNT_DELETE_REQUESTED: AccountDeleteRequested,
    WebhookEventAsyncType.ACCOUNT_DELETED: AccountDeleted,
    WebhookEventAsyncType.ADDRESS_CREATED: AddressCreated,
    WebhookEventAsyncType.ADDRESS_UPDATED: AddressUpdated,
    WebhookEventAsyncType.ADDRESS_DELETED: AddressDeleted,
    WebhookEventAsyncType.APP_INSTALLED: AppInstalled,
    WebhookEventAsyncType.APP_UPDATED: AppUpdated,
    WebhookEventAsyncType.APP_DELETED: AppDeleted,
    WebhookEventAsyncType.APP_STATUS_CHANGED: AppStatusChanged,
    WebhookEventAsyncType.CHANNEL_CREATED: ChannelCreated,
    WebhookEventAsyncType.CHANNEL_UPDATED: ChannelUpdated,
    WebhookEventAsyncType.CHANNEL_DELETED: ChannelDeleted,
    WebhookEventAsyncType.CHANNEL_STATUS_CHANGED: ChannelStatusChanged,
    WebhookEventAsyncType.CHANNEL_METADATA_UPDATED: ChannelMetadataUpdated,
    WebhookEventAsyncType.MENU_CREATED: MenuCreated,
    WebhookEventAsyncType.MENU_UPDATED: MenuUpdated,
    WebhookEventAsyncType.MENU_DELETED: MenuDeleted,
    WebhookEventAsyncType.MENU_ITEM_CREATED: MenuItemCreated,
    WebhookEventAsyncType.MENU_ITEM_UPDATED: MenuItemUpdated,
    WebhookEventAsyncType.MENU_ITEM_DELETED: MenuItemDeleted,
    WebhookEventAsyncType.CUSTOMER_CREATED: CustomerCreated,
    WebhookEventAsyncType.CUSTOMER_UPDATED: CustomerUpdated,
    WebhookEventAsyncType.CUSTOMER_METADATA_UPDATED: CustomerMetadataUpdated,
    WebhookEventAsyncType.PERMISSION_GROUP_CREATED: PermissionGroupCreated,
    WebhookEventAsyncType.PERMISSION_GROUP_UPDATED: PermissionGroupUpdated,
    WebhookEventAsyncType.PERMISSION_GROUP_DELETED: PermissionGroupDeleted,
    WebhookEventAsyncType.STAFF_CREATED: StaffCreated,
    WebhookEventAsyncType.STAFF_UPDATED: StaffUpdated,
    WebhookEventAsyncType.STAFF_DELETED: StaffDeleted,
    WebhookEventAsyncType.STAFF_SET_PASSWORD_REQUESTED: StaffSetPasswordRequested,
    WebhookEventAsyncType.TRANSACTION_ITEM_METADATA_UPDATED: (
        TransactionItemMetadataUpdated
    ),
    WebhookEventAsyncType.THUMBNAIL_CREATED: ThumbnailCreated,
}

WEBHOOK_TYPES_MAP = ASYNC_WEBHOOK_TYPES_MAP | SYNC_WEBHOOK_TYPES_MAP
