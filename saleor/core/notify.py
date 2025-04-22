from functools import cache
from typing import Callable


class NotifyHandler:
    """Helper class for handling payload generation for notify event.

    Payload is generated only when required and only once for the instance.
    In case when plugins/webhooks don't use notfiy event, payload is not generated.
    """

    generate_payload_func: Callable[[], dict]

    def __init__(self, payload_func):
        self.generate_payload_func = payload_func

    @cache
    def payload(self):
        return self.generate_payload_func()


class UserNotifyEvent:
    ACCOUNT_CONFIRMATION = "account_confirmation"
    ACCOUNT_PASSWORD_RESET = "account_password_reset"
    ACCOUNT_CHANGE_EMAIL_REQUEST = "account_change_email_request"
    ACCOUNT_CHANGE_EMAIL_CONFIRM = "account_change_email_confirm"
    ACCOUNT_DELETE = "account_delete"
    ACCOUNT_SET_CUSTOMER_PASSWORD = "account_set_customer_password"

    CHOICES = [
        ACCOUNT_CONFIRMATION,
        ACCOUNT_PASSWORD_RESET,
        ACCOUNT_CHANGE_EMAIL_REQUEST,
        ACCOUNT_CHANGE_EMAIL_CONFIRM,
        ACCOUNT_DELETE,
        ACCOUNT_SET_CUSTOMER_PASSWORD,
    ]


class AdminNotifyEvent:
    ACCOUNT_SET_STAFF_PASSWORD = "account_set_staff_password"
    ACCOUNT_STAFF_RESET_PASSWORD = "account_staff_reset_password"
    CSV_EXPORT_SUCCESS = "csv_export_success"
    CSV_EXPORT_FAILED = "csv_export_failed"
    STAFF_ORDER_CONFIRMATION = "staff_order_confirmation"

    CHOICES = [
        ACCOUNT_SET_STAFF_PASSWORD,
        CSV_EXPORT_SUCCESS,
        CSV_EXPORT_FAILED,
        STAFF_ORDER_CONFIRMATION,
        ACCOUNT_STAFF_RESET_PASSWORD,
    ]


class NotifyEventType(UserNotifyEvent, AdminNotifyEvent):
    CHOICES = UserNotifyEvent.CHOICES + AdminNotifyEvent.CHOICES
