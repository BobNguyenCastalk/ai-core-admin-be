import graphene

from ...webhook.event_types import WebhookEventAsyncType, WebhookEventSyncType
from ..core.descriptions import (
    ADDED_IN_38,
    DEPRECATED_IN_3X_ENUM_VALUE,
)
from ..core.doc_category import DOC_CATEGORY_WEBHOOKS
from ..core.types import BaseEnum
from ..core.utils import str_to_enum

checkout_updated_event_enum_description = (
    "A checkout is updated. It also triggers all updates related to the checkout."
)

order_confirmed_event_enum_description = (
    "An order is confirmed (status change unconfirmed -> unfulfilled) "
    "by a staff user using the OrderConfirm mutation. "
    "It also triggers when the user completes the checkout and the shop "
    "setting `automatically_confirm_all_new_orders` is enabled."
)

order_fully_paid_event_enum_description = "Payment is made and an order is fully paid."

order_updated_event_enum_description = (
    "An order is updated; triggered for all changes related to an order; "
    "covers all other order webhooks, except for ORDER_CREATED."
)


WEBHOOK_EVENT_DESCRIPTION = {
    WebhookEventAsyncType.ACCOUNT_CONFIRMATION_REQUESTED: (
        "An account confirmation is requested."
    ),
    WebhookEventAsyncType.ACCOUNT_EMAIL_CHANGED: "An account email was changed",
    WebhookEventAsyncType.ACCOUNT_CHANGE_EMAIL_REQUESTED: (
        "An account email change is requested."
    ),
    WebhookEventAsyncType.ACCOUNT_SET_PASSWORD_REQUESTED: (
        "Setting a new password for the account is requested."
    ),
    WebhookEventAsyncType.ACCOUNT_CONFIRMED: "An account is confirmed.",
    WebhookEventAsyncType.ACCOUNT_DELETE_REQUESTED: "An account delete is requested.",
    WebhookEventAsyncType.ACCOUNT_DELETED: "An account is deleted.",
    WebhookEventAsyncType.APP_INSTALLED: "A new app installed.",
    WebhookEventAsyncType.APP_UPDATED: "An app updated.",
    WebhookEventAsyncType.APP_DELETED: "An app deleted.",
    WebhookEventAsyncType.APP_STATUS_CHANGED: "An app status is changed.",
    WebhookEventAsyncType.CHANNEL_CREATED: "A new channel created.",
    WebhookEventAsyncType.CHANNEL_UPDATED: "A channel is updated.",
    WebhookEventAsyncType.CHANNEL_DELETED: "A channel is deleted.",
    WebhookEventAsyncType.CHANNEL_STATUS_CHANGED: "A channel status is changed.",
    WebhookEventAsyncType.CHANNEL_METADATA_UPDATED: "A channel metadata is updated.",
    WebhookEventAsyncType.CUSTOMER_CREATED: "A new customer account is created.",
    WebhookEventAsyncType.CUSTOMER_UPDATED: "A customer account is updated.",
    WebhookEventAsyncType.CUSTOMER_DELETED: "A customer account is deleted.",
    WebhookEventAsyncType.CUSTOMER_METADATA_UPDATED: (
        "A customer account metadata is updated." + ADDED_IN_38
    ),
    WebhookEventAsyncType.MENU_CREATED: "A new menu created.",
    WebhookEventAsyncType.MENU_UPDATED: "A menu is updated.",
    WebhookEventAsyncType.MENU_DELETED: "A menu is deleted.",
    WebhookEventAsyncType.MENU_ITEM_CREATED: "A new menu item created.",
    WebhookEventAsyncType.MENU_ITEM_UPDATED: "A menu item is updated.",
    WebhookEventAsyncType.MENU_ITEM_DELETED: "A menu item is deleted.",
    WebhookEventAsyncType.NOTIFY_USER: (
        "User notification triggered."
        + DEPRECATED_IN_3X_ENUM_VALUE
        + " See the docs for more details about migrating from NOTIFY_USER to other "
        "events: "
        + "https://docs.saleor.io/docs/next/upgrade-guides/notify-user-deprecation"
    ),
    WebhookEventAsyncType.PERMISSION_GROUP_CREATED: (
        "A new permission group is created."
    ),
    WebhookEventAsyncType.PERMISSION_GROUP_UPDATED: "A permission group is updated.",
    WebhookEventAsyncType.PERMISSION_GROUP_DELETED: "A permission group is deleted.",
    WebhookEventAsyncType.STAFF_SET_PASSWORD_REQUESTED: (
        "Setting a new password for the staff account is requested."
    ),
    WebhookEventAsyncType.STAFF_CREATED: "A new staff user is created.",
    WebhookEventAsyncType.STAFF_UPDATED: "A staff user is updated.",
    WebhookEventAsyncType.STAFF_DELETED: "A staff user is deleted.",
    WebhookEventAsyncType.ANY: "All the events." + DEPRECATED_IN_3X_ENUM_VALUE,
    WebhookEventAsyncType.OBSERVABILITY: "An observability event is created.",
}


def description(enum):
    if enum:
        return WEBHOOK_EVENT_DESCRIPTION.get(enum.value)
    return "Enum determining type of webhook."


WebhookEventTypeEnum = graphene.Enum(
    "WebhookEventTypeEnum",
    [
        (str_to_enum(e_type[0]), e_type[0])
        for e_type in (WebhookEventAsyncType.CHOICES + WebhookEventSyncType.CHOICES)
    ],
    description=description,
)
WebhookEventTypeEnum.doc_category = DOC_CATEGORY_WEBHOOKS


WebhookEventTypeAsyncEnum = graphene.Enum(
    "WebhookEventTypeAsyncEnum",
    [(str_to_enum(e_type[0]), e_type[0]) for e_type in WebhookEventAsyncType.CHOICES],
    description=description,
)
WebhookEventTypeAsyncEnum.doc_category = DOC_CATEGORY_WEBHOOKS

WebhookSampleEventTypeEnum = graphene.Enum(
    "WebhookSampleEventTypeEnum",
    [
        (str_to_enum(e_type[0]), e_type[0])
        for e_type in WebhookEventAsyncType.CHOICES
        if e_type[0] != WebhookEventAsyncType.ANY
    ],
)
WebhookSampleEventTypeEnum.doc_category = DOC_CATEGORY_WEBHOOKS


class EventDeliveryStatusEnum(BaseEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"

    class Meta:
        doc_category = DOC_CATEGORY_WEBHOOKS
