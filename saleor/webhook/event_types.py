from typing import Any, Optional

from ..permission.enums import (
    AccountPermissions,
    AppPermission,
    BasePermissionEnum,
    ChannelPermissions,
    MenuPermissions,
)


class WebhookEventAsyncType:
    ANY = "any_events"

    ACCOUNT_CONFIRMATION_REQUESTED = "account_confirmation_requested"
    ACCOUNT_EMAIL_CHANGED = "account_email_changed"
    ACCOUNT_CHANGE_EMAIL_REQUESTED = "account_change_email_requested"
    ACCOUNT_SET_PASSWORD_REQUESTED = "account_set_password_requested"
    ACCOUNT_CONFIRMED = "account_confirmed"
    ACCOUNT_DELETE_REQUESTED = "account_delete_requested"
    ACCOUNT_DELETED = "account_deleted"

    APP_INSTALLED = "app_installed"
    APP_UPDATED = "app_updated"
    APP_DELETED = "app_deleted"
    APP_STATUS_CHANGED = "app_status_changed"

    CHANNEL_CREATED = "channel_created"
    CHANNEL_UPDATED = "channel_updated"
    CHANNEL_DELETED = "channel_deleted"
    CHANNEL_STATUS_CHANGED = "channel_status_changed"
    CHANNEL_METADATA_UPDATED = "channel_metadata_updated"

    MENU_CREATED = "menu_created"
    MENU_UPDATED = "menu_updated"
    MENU_DELETED = "menu_deleted"
    MENU_ITEM_CREATED = "menu_item_created"
    MENU_ITEM_UPDATED = "menu_item_updated"
    MENU_ITEM_DELETED = "menu_item_deleted"

    CUSTOMER_CREATED = "customer_created"
    CUSTOMER_UPDATED = "customer_updated"
    CUSTOMER_DELETED = "customer_deleted"
    CUSTOMER_METADATA_UPDATED = "customer_metadata_updated"

    NOTIFY_USER = "notify_user"  # deprecated

    PERMISSION_GROUP_CREATED = "permission_group_created"
    PERMISSION_GROUP_UPDATED = "permission_group_updated"
    PERMISSION_GROUP_DELETED = "permission_group_deleted"

    STAFF_CREATED = "staff_created"
    STAFF_UPDATED = "staff_updated"
    STAFF_DELETED = "staff_deleted"
    STAFF_SET_PASSWORD_REQUESTED = "staff_set_password_requested"
    OBSERVABILITY = "observability"

    EVENT_MAP: dict[str, dict[str, Any]] = {
        ACCOUNT_CONFIRMATION_REQUESTED: {
            "name": "Account confirmation requested",
            "permission": AccountPermissions.MANAGE_USERS,
        },
        ACCOUNT_CHANGE_EMAIL_REQUESTED: {
            "name": "Account change email requested",
            "permission": AccountPermissions.MANAGE_USERS,
        },
        ACCOUNT_EMAIL_CHANGED: {
            "name": "Account email changed",
            "permission": AccountPermissions.MANAGE_USERS,
        },
        ACCOUNT_SET_PASSWORD_REQUESTED: {
            "name": "Account set password requested",
            "permission": AccountPermissions.MANAGE_USERS,
        },
        ACCOUNT_CONFIRMED: {
            "name": "Account confirmed",
            "permission": AccountPermissions.MANAGE_USERS,
        },
        ACCOUNT_DELETE_REQUESTED: {
            "name": "Account delete requested",
            "permission": AccountPermissions.MANAGE_USERS,
        },
        ACCOUNT_DELETED: {
            "name": "Account delete confirmed",
            "permission": AccountPermissions.MANAGE_USERS,
        },
        APP_INSTALLED: {
            "name": "App created",
            "permission": AppPermission.MANAGE_APPS,
        },
        APP_UPDATED: {
            "name": "App updated",
            "permission": AppPermission.MANAGE_APPS,
        },
        APP_DELETED: {
            "name": "App deleted",
            "permission": AppPermission.MANAGE_APPS,
        },
        APP_STATUS_CHANGED: {
            "name": "App status changed",
            "permission": AppPermission.MANAGE_APPS,
        },
        CHANNEL_CREATED: {
            "name": "Channel created",
            "permission": ChannelPermissions.MANAGE_CHANNELS,
        },
        CHANNEL_UPDATED: {
            "name": "Channel updated",
            "permission": ChannelPermissions.MANAGE_CHANNELS,
        },
        CHANNEL_DELETED: {
            "name": "Channel deleted",
            "permission": ChannelPermissions.MANAGE_CHANNELS,
        },
        CHANNEL_STATUS_CHANGED: {
            "name": "Channel status changed",
            "permission": ChannelPermissions.MANAGE_CHANNELS,
        },
        CHANNEL_METADATA_UPDATED: {
            "name": "Channel metadata updated",
            "permission": ChannelPermissions.MANAGE_CHANNELS,
        },
        MENU_CREATED: {
            "name": "Menu created",
            "permission": MenuPermissions.MANAGE_MENUS,
        },
        MENU_UPDATED: {
            "name": "Menu updated",
            "permission": MenuPermissions.MANAGE_MENUS,
        },
        MENU_DELETED: {
            "name": "Menu deleted",
            "permission": MenuPermissions.MANAGE_MENUS,
        },
        MENU_ITEM_CREATED: {
            "name": "Menu item created",
            "permission": MenuPermissions.MANAGE_MENUS,
        },
        MENU_ITEM_UPDATED: {
            "name": "Menu item updated",
            "permission": MenuPermissions.MANAGE_MENUS,
        },
        MENU_ITEM_DELETED: {
            "name": "Menu item deleted",
            "permission": MenuPermissions.MANAGE_MENUS,
        },
        CUSTOMER_CREATED: {
            "name": "Customer created",
            "permission": AccountPermissions.MANAGE_USERS,
        },
        CUSTOMER_UPDATED: {
            "name": "Customer updated",
            "permission": AccountPermissions.MANAGE_USERS,
        },
        CUSTOMER_DELETED: {
            "name": "Customer deleted",
            "permission": AccountPermissions.MANAGE_USERS,
        },
        CUSTOMER_METADATA_UPDATED: {
            "name": "Customer metadata updated",
            "permission": AccountPermissions.MANAGE_USERS,
        },
        NOTIFY_USER: {
            "name": "Notify user",
            "permission": AccountPermissions.MANAGE_USERS,
        },
        PERMISSION_GROUP_CREATED: {
            "name": "Permission group created",
            "permission": AccountPermissions.MANAGE_STAFF,
        },
        PERMISSION_GROUP_UPDATED: {
            "name": "Permission group updated",
            "permission": AccountPermissions.MANAGE_STAFF,
        },
        PERMISSION_GROUP_DELETED: {
            "name": "Permission group deleted",
            "permission": AccountPermissions.MANAGE_STAFF,
        },
        STAFF_CREATED: {
            "name": "Staff created",
            "permission": AccountPermissions.MANAGE_STAFF,
        },
        STAFF_UPDATED: {
            "name": "Staff updated",
            "permission": AccountPermissions.MANAGE_STAFF,
        },
        STAFF_DELETED: {
            "name": "Staff deleted",
            "permission": AccountPermissions.MANAGE_STAFF,
        },
        STAFF_SET_PASSWORD_REQUESTED: {
            "name": "Setting a password for a staff is requested",
            "permission": AccountPermissions.MANAGE_STAFF,
        },
        OBSERVABILITY: {
            "name": "Observability",
            "permission": AppPermission.MANAGE_OBSERVABILITY,
        },
    }

    CHOICES = [
        (ANY, "Any events"),
    ] + [
        (event_name, event_data["name"]) for event_name, event_data in EVENT_MAP.items()
    ]
    PERMISSIONS: dict[str, Optional[BasePermissionEnum]] = {
        event_name: event_data["permission"]
        for event_name, event_data in EVENT_MAP.items()
    }

    ALL = [event[0] for event in CHOICES]


class WebhookEventSyncType:
 

    EVENT_MAP: dict[str, dict[str, Any]] = {
    }

    CHOICES = [
        (event_name, event_data["name"]) for event_name, event_data in EVENT_MAP.items()
    ]
    PERMISSIONS: dict[str, Optional[BasePermissionEnum]] = {
        event_name: event_data["permission"]
        for event_name, event_data in EVENT_MAP.items()
    }

    ALL = [event[0] for event in CHOICES]

