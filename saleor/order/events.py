from decimal import Decimal
from typing import TYPE_CHECKING, Optional, Union

from ..account import events as account_events
from ..account.models import User
from ..app.models import App
from ..order.models import Fulfillment, FulfillmentLine, Order, OrderLine
from ..payment.models import Payment
from . import OrderEvents, OrderEventsEmails
from .models import OrderEvent

if TYPE_CHECKING:
    from uuid import UUID


def _line_per_quantity_to_line_object(quantity, line):
    return {"quantity": quantity, "line_pk": line.pk, "item": str(line)}


def _lines_per_quantity_to_line_object_list(order_lines):
    return [
        _line_per_quantity_to_line_object(line.quantity, line) for line in order_lines
    ]


def _get_payment_data(amount: Optional[Decimal], payment: Payment) -> dict:
    return {
        "parameters": {
            "amount": amount,
            "payment_id": payment.token,
            "payment_gateway": payment.gateway,
        }
    }


def event_transaction_charge_requested(
    order_id: "UUID",
    reference: str,
    amount: Decimal,
    user: Optional[User],
    app: Optional[App],
):
    return OrderEvent.objects.create(
        order_id=order_id,
        type=OrderEvents.TRANSACTION_CHARGE_REQUESTED,
        user=user,
        app=app,
        parameters={
            "amount": amount,
            "reference": reference,
        },
    )


def event_transaction_refund_requested(
    order_id: "UUID",
    reference: str,
    amount: Decimal,
    user: Optional[User],
    app: Optional[App],
):
    return OrderEvent.objects.create(
        order_id=order_id,
        type=OrderEvents.TRANSACTION_REFUND_REQUESTED,
        user=user,
        app=app,
        parameters={
            "amount": amount,
            "reference": reference,
        },
    )


def event_transaction_cancel_requested(
    order_id: "UUID", reference: str, user: Optional[User], app: Optional[App]
):
    return OrderEvent.objects.create(
        order_id=order_id,
        type=OrderEvents.TRANSACTION_CANCEL_REQUESTED,
        user=user,
        app=app,
        parameters={
            "reference": reference,
        },
    )


def event_order_refunded_notification(
    order_id: "UUID", user_id: Optional[int], app_id: Optional[int], customer_email: str
):
    return OrderEvent.objects.create(
        order_id=order_id,
        type=OrderEvents.EMAIL_SENT,
        parameters={
            "email": customer_email,
            "email_type": OrderEventsEmails.ORDER_REFUND,
        },
        user_id=user_id,
        app_id=app_id,
    )


def event_order_confirmed_notification(
    order_id: "UUID", user_id: Optional[int], app_id: Optional[int], customer_email: str
):
    return OrderEvent.objects.create(
        order_id=order_id,
        type=OrderEvents.EMAIL_SENT,
        parameters={
            "email": customer_email,
            "email_type": OrderEventsEmails.CONFIRMED,
        },
        user_id=user_id,
        app_id=app_id,
    )


def event_order_cancelled_notification(
    order_id: "UUID", user_id: Optional[int], app_id: Optional[int], customer_email: str
):
    return OrderEvent.objects.create(
        order_id=order_id,
        type=OrderEvents.EMAIL_SENT,
        parameters={
            "email": customer_email,
            "email_type": OrderEventsEmails.ORDER_CANCEL,
        },
        user_id=user_id,
        app_id=app_id,
    )


def event_order_confirmation_notification(
    order_id: "UUID", user_id: Optional[int], customer_email: str
):
    return OrderEvent.objects.create(
        order_id=order_id,
        type=OrderEvents.EMAIL_SENT,
        parameters={
            "email": customer_email,
            "email_type": OrderEventsEmails.ORDER_CONFIRMATION,
        },
        user_id=user_id,
    )


def event_fulfillment_confirmed_notification(
    order_id: "UUID", user_id: Optional[int], app_id: Optional[int], customer_email: str
):
    return OrderEvent.objects.create(
        order_id=order_id,
        type=OrderEvents.EMAIL_SENT,
        parameters={
            "email": customer_email,
            "email_type": OrderEventsEmails.FULFILLMENT,
        },
        user_id=user_id,
        app_id=app_id,
    )


def event_fulfillment_digital_links_notification(
    order_id: "UUID", user_id: Optional[int], app_id: Optional[int], customer_email: str
):
    return OrderEvent.objects.create(
        order_id=order_id,
        type=OrderEvents.EMAIL_SENT,
        parameters={
            "email": customer_email,
            "email_type": OrderEventsEmails.DIGITAL_LINKS,
        },
        user_id=user_id,
        app_id=app_id,
    )


def event_payment_confirmed_notification(
    order_id: "UUID", user_id: Optional[int], customer_email: str
):
    return OrderEvent.objects.create(
        order_id=order_id,
        type=OrderEvents.EMAIL_SENT,
        parameters={"email": customer_email, "email_type": OrderEventsEmails.PAYMENT},
        user_id=user_id,
    )

def email_resent_event(
    *, order: Order, user: Optional[User], email_type: OrderEventsEmails
) -> OrderEvent:
    raise NotImplementedError


def draft_order_created_event(
    *, order: Order, user: Optional[User], app: Optional[App]
) -> OrderEvent:
    return OrderEvent.objects.create(
        order=order, type=OrderEvents.DRAFT_CREATED, user=user, app=app
    )


def order_added_products_event(
    *,
    order: Order,
    user: Optional[User],
    app: Optional[App],
    order_lines: list[OrderLine],
    quantity_diff: Optional[int] = None,
) -> OrderEvent:
    if quantity_diff:
        lines = [_line_per_quantity_to_line_object(quantity_diff, order_lines[0])]
    else:
        lines = _lines_per_quantity_to_line_object_list(order_lines)

    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.ADDED_PRODUCTS,
        user=user,
        app=app,
        parameters={"lines": lines},
    )


def order_removed_products_event(
    *,
    order: Order,
    user: Optional[User],
    app: Optional[App],
    order_lines: list[OrderLine],
    quantity_diff: Optional[int] = None,
) -> OrderEvent:
    if quantity_diff:
        lines = [_line_per_quantity_to_line_object(quantity_diff, order_lines[0])]
    else:
        lines = _lines_per_quantity_to_line_object_list(order_lines)

    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.REMOVED_PRODUCTS,
        user=user,
        app=app,
        parameters={"lines": lines},
    )


def draft_order_created_from_replace_event(
    *,
    draft_order: Order,
    original_order: Order,
    user: Optional[User],
    app: Optional[App],
    lines: list[OrderLine],
):
    parameters = {
        "related_order_pk": original_order.pk,
        "lines": _lines_per_quantity_to_line_object_list(lines),
    }
    return OrderEvent.objects.create(
        order=draft_order,
        type=OrderEvents.DRAFT_CREATED_FROM_REPLACE,
        user=user,
        app=app,
        parameters=parameters,
    )


def order_created_event(
    *,
    order: Order,
    user: Optional[User],
    app: Optional[App],
    from_draft=False,
    automatic=False,
) -> OrderEvent:
    if from_draft:
        event_type = OrderEvents.PLACED_FROM_DRAFT
    elif automatic:
        event_type = OrderEvents.PLACED_AUTOMATICALLY_FROM_PAID_CHECKOUT
    else:
        event_type = OrderEvents.PLACED
        if user:
            account_events.customer_placed_order_event(
                user=user,
                order=order,
            )

    return OrderEvent.objects.create(order=order, type=event_type, user=user, app=app)


def order_confirmed_event(
    *, order: Order, user: Optional[User], app: Optional[App]
) -> OrderEvent:
    return OrderEvent.objects.create(
        order=order, type=OrderEvents.CONFIRMED, user=user, app=app
    )


def order_canceled_event(
    *, order: Order, user: Optional[User], app: Optional[App]
) -> OrderEvent:
    return OrderEvent.objects.create(
        order=order, type=OrderEvents.CANCELED, user=user, app=app
    )


def order_manually_marked_as_paid_event(
    *,
    order: Order,
    user: Optional[User],
    app: Optional[App],
    transaction_reference: Optional[str] = None,
) -> OrderEvent:
    parameters = {}
    if transaction_reference:
        parameters = {"transaction_reference": transaction_reference}
    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.ORDER_MARKED_AS_PAID,
        user=user,
        app=app,
        parameters=parameters,
    )


def order_fully_paid_event(
    *,
    order: Order,
    user: Optional[User],
    app: Optional[App],
    gateway: Optional[str] = None,
) -> OrderEvent:
    parameters = {}
    if gateway:
        parameters = {"payment_gateway": gateway}
    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.ORDER_FULLY_PAID,
        user=user,
        app=app,
        parameters=parameters,
    )


def order_replacement_created(
    *,
    original_order: Order,
    replace_order: Order,
    user: Optional[User],
    app: Optional[App],
) -> OrderEvent:
    parameters = {"related_order_pk": replace_order.pk}
    return OrderEvent.objects.create(
        order=original_order,
        type=OrderEvents.ORDER_REPLACEMENT_CREATED,
        user=user,
        app=app,
        parameters=parameters,
    )


def payment_authorized_event(
    *,
    order: Order,
    user: Optional[User],
    app: Optional[App],
    amount: Decimal,
    payment: Payment,
) -> OrderEvent:
    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.PAYMENT_AUTHORIZED,
        user=user,
        app=app,
        **_get_payment_data(amount, payment),
    )


def payment_captured_event(
    *,
    order: Order,
    user: Optional[User],
    app: Optional[App],
    amount: Decimal,
    payment: Payment,
) -> OrderEvent:
    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.PAYMENT_CAPTURED,
        user=user,
        app=app,
        **_get_payment_data(amount, payment),
    )


def payment_refunded_event(
    *,
    order: Order,
    user: Optional[User],
    app: Optional[App],
    amount: Decimal,
    payment: Payment,
) -> OrderEvent:
    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.PAYMENT_REFUNDED,
        user=user,
        app=app,
        **_get_payment_data(amount, payment),
    )


def payment_voided_event(
    *, order: Order, user: Optional[User], app: Optional[App], payment: Payment
) -> OrderEvent:
    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.PAYMENT_VOIDED,
        user=user,
        app=app,
        **_get_payment_data(None, payment),
    )


def payment_failed_event(
    *,
    order: Order,
    user: Optional[User],
    app: Optional[App],
    message: str,
    payment: Payment,
) -> OrderEvent:
    parameters = {"message": message}

    if payment:
        parameters.update({"gateway": payment.gateway, "payment_id": payment.token})

    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.PAYMENT_FAILED,
        user=user,
        app=app,
        parameters=parameters,
    )


def transaction_mark_order_as_paid_failed_event(
    order: Order, user: Optional[User], app: Optional[App], message: str
):
    parameters = {"message": message}

    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.TRANSACTION_MARK_AS_PAID_FAILED,
        user=user,
        app=app,
        parameters=parameters,
    )


def transaction_event(
    *,
    order: Order,
    user: Optional[User],
    app: Optional[App],
    reference: str,
    message: str,
) -> OrderEvent:
    parameters = {"message": message, "reference": reference}
    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.TRANSACTION_EVENT,
        user=user,
        app=app,
        parameters=parameters,
    )


def external_notification_event(
    *,
    order: Order,
    user: Optional[User],
    app: Optional[App],
    message: Optional[str],
    parameters: Optional[dict],
) -> OrderEvent:
    parameters = parameters or {}
    parameters["message"] = message

    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.EXTERNAL_SERVICE_NOTIFICATION,
        user=user,
        app=app,
        parameters=parameters,
    )


def fulfillment_canceled_event(
    *,
    order: Order,
    user: Optional[User],
    app: Optional[App],
    fulfillment: Optional[Fulfillment],
) -> OrderEvent:
    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.FULFILLMENT_CANCELED,
        user=user,
        app=app,
        parameters={"composed_id": fulfillment.composed_id} if fulfillment else {},
    )


def fulfillment_restocked_items_event(
    *,
    order: Order,
    user: Optional[User],
    app: Optional[App],
    fulfillment: Union[Order, Fulfillment],
    warehouse_pk: Optional["UUID"] = None,
) -> OrderEvent:
    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.FULFILLMENT_RESTOCKED_ITEMS,
        user=user,
        app=app,
        parameters={
            "quantity": fulfillment.get_total_quantity(),
            "warehouse": warehouse_pk,
        },
    )


def fulfillment_fulfilled_items_event(
    *,
    order: Order,
    user: Optional[User],
    app: Optional[App],
    fulfillment_lines: list[FulfillmentLine],
    auto: bool = False,
) -> OrderEvent:
    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.FULFILLMENT_FULFILLED_ITEMS,
        user=user,
        app=app,
        parameters={
            "fulfilled_items": [line.pk for line in fulfillment_lines],
            "auto": auto,
        },
    )


def fulfillment_awaits_approval_event(
    *,
    order: Order,
    user: Optional[User],
    app: Optional[App],
    fulfillment_lines: list[FulfillmentLine],
) -> OrderEvent:
    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.FULFILLMENT_AWAITS_APPROVAL,
        user=user,
        app=app,
        parameters={"awaiting_fulfillments": [line.pk for line in fulfillment_lines]},
    )


def order_returned_event(
    *,
    order: Order,
    user: Optional[User],
    app: Optional[App],
    returned_lines: list[tuple[int, OrderLine]],
):
    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.FULFILLMENT_RETURNED,
        user=user,
        app=app,
        parameters={
            "lines": [
                _line_per_quantity_to_line_object(quantity, line)
                for quantity, line in returned_lines
            ]
        },
    )


def fulfillment_replaced_event(
    *,
    order: Order,
    user: Optional[User],
    app: Optional[App],
    replaced_lines: list[OrderLine],
):
    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.FULFILLMENT_REPLACED,
        user=user,
        app=app,
        parameters={"lines": _lines_per_quantity_to_line_object_list(replaced_lines)},
    )


def fulfillment_refunded_event(
    *,
    order: Order,
    user: Optional[User],
    app: Optional[App],
    refunded_lines: list[tuple[int, OrderLine]],
    amount: Decimal,
    shipping_costs_included: bool,
):
    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.FULFILLMENT_REFUNDED,
        user=user,
        app=app,
        parameters={
            "lines": [
                _line_per_quantity_to_line_object(quantity, line)
                for quantity, line in refunded_lines
            ],
            "amount": amount,
            "shipping_costs_included": shipping_costs_included,
        },
    )


def fulfillment_tracking_updated_event(
    *,
    order: Order,
    user: Optional[User],
    app: Optional[App],
    tracking_number: str,
    fulfillment: Fulfillment,
) -> OrderEvent:
    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.TRACKING_UPDATED,
        user=user,
        app=app,
        parameters={
            "tracking_number": tracking_number,
            "fulfillment": fulfillment.composed_id,
        },
    )


def order_note_added_event(
    *, order: Order, user: Optional[User], app: Optional[App], message: str
) -> OrderEvent:
    kwargs: dict[str, Union[Optional[App], Optional[User]]] = {"app": app}
    if user is not None:
        if order.user is not None and order.user.pk == user.pk:
            account_events.customer_added_to_note_order_event(
                user=user, order=order, message=message
            )
        kwargs["user"] = user

    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.NOTE_ADDED,
        parameters={"message": message},
        **kwargs,
    )


def order_note_updated_event(
    *,
    order: Order,
    user: Optional[User],
    app: Optional[App],
    message: str,
    related_event: OrderEvent,
) -> OrderEvent:
    return OrderEvent.objects.create(
        order=order,
        type=OrderEvents.NOTE_UPDATED,
        parameters={"message": message},
        app=app,
        user=user,
        related=related_event,
    )


def order_line_product_removed_event(
    order: Order,
    user: Optional[User],
    app: Optional[App],
    order_lines: list[tuple[int, OrderLine]],
):
    return OrderEvent.objects.create(
        type=OrderEvents.ORDER_LINE_PRODUCT_DELETED,
        order=order,
        user=user,
        app=app,
        parameters={"lines": _lines_per_quantity_to_line_object_list(order_lines)},
    )


def order_line_variant_removed_event(
    order: Order,
    user: Optional[User],
    app: Optional[App],
    order_lines: list[tuple[int, OrderLine]],
):
    return OrderEvent.objects.create(
        type=OrderEvents.ORDER_LINE_VARIANT_DELETED,
        order=order,
        user=user,
        app=app,
        parameters={"lines": _lines_per_quantity_to_line_object_list(order_lines)},
    )
