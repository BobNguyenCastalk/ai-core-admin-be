import json
import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
)

import graphene
from django.db.models import F, QuerySet, Sum
from django.utils import timezone
from graphene.utils.str_converters import to_camel_case

from .. import __version__
from ..account.models import User
from ..attribute.models import AttributeValueTranslation
from ..core.db.connection import allow_writer
from ..core.prices import quantize_price, quantize_price_fields
from ..core.utils.anonymization import (
    generate_fake_user,
)
from ..core.utils.json_serializer import CustomJsonEncoder
from ..page.models import Page
from ..thumbnail.models import Thumbnail
from . import traced_payload_generator
from .event_types import WebhookEventAsyncType
from .payload_serializers import PayloadSerializer
from .serializers import (
    serialize_checkout_lines,
)

if TYPE_CHECKING:
    from ..discount.models import Promotion
    from ..payment.interface import (
        PaymentData,
        TransactionActionData,
    )
    from ..plugins.base_plugin import RequestorOrLazyObject
    from ..translation.models import Translation


ADDRESS_FIELDS = (
    "first_name",
    "last_name",
    "company_name",
    "street_address_1",
    "street_address_2",
    "city",
    "city_area",
    "postal_code",
    "country",
    "country_area",
    "phone",
)

CHANNEL_FIELDS = ("slug", "currency_code")

ORDER_FIELDS = (
    "status",
    "origin",
    "shipping_method_name",
    "collection_point_name",
    "shipping_price_net_amount",
    "shipping_price_gross_amount",
    "shipping_tax_rate",
    "weight",
    "language_code",
    "private_metadata",
    "metadata",
    "total_net_amount",
    "total_gross_amount",
    "undiscounted_total_net_amount",
    "undiscounted_total_gross_amount",
)

ORDER_PRICE_FIELDS = (
    "shipping_price_net_amount",
    "shipping_price_gross_amount",
    "total_net_amount",
    "total_gross_amount",
    "undiscounted_total_net_amount",
    "undiscounted_total_gross_amount",
)


def generate_requestor(requestor: Optional["RequestorOrLazyObject"] = None):
    if not requestor:
        return {"id": None, "type": None}
    if isinstance(requestor, User):
        return {"id": graphene.Node.to_global_id("User", requestor.id), "type": "user"}
    return {"id": requestor.name, "type": "app"}  # type: ignore


def generate_meta(*, requestor_data: dict[str, Any], camel_case=False, **kwargs):
    meta_result = {
        "issued_at": timezone.now().isoformat(),
        "version": __version__,
        "issuing_principal": requestor_data,
    }

    meta_result.update(kwargs)

    if camel_case:
        meta = {}
        for key, value in meta_result.items():
            meta[to_camel_case(key)] = value
    else:
        meta = meta_result

    return meta


@allow_writer()
@traced_payload_generator
def generate_metadata_updated_payload(
    instance: Any, requestor: Optional["RequestorOrLazyObject"] = None
):
    serializer = PayloadSerializer()


    pk_field_name = "id"
    return serializer.serialize(
        [instance],
        fields=[],
        pk_field_name=pk_field_name,
        extra_dict_data={
            "meta": generate_meta(requestor_data=generate_requestor(requestor)),
        },
        dump_type_name=False,
    )


def prepare_order_lines_allocations_payload(line):
    warehouse_id_quantity_allocated_map = list(
        line.allocations.values(
            "quantity_allocated", warehouse_id=F("stock__warehouse_id")
        )
    )
    return warehouse_id_quantity_allocated_map


def _generate_shipping_method_payload(shipping_method, channel):
    if not shipping_method:
        return None

    shipping_method_channel_listing = shipping_method.channel_listings.filter(
        channel=channel,
    ).first()

    if not shipping_method_channel_listing:
        return None

    serializer = PayloadSerializer()
    shipping_method_fields = ("name", "type")

    payload = serializer.serialize(
        [shipping_method],
        fields=shipping_method_fields,
        extra_dict_data={
            "currency": shipping_method_channel_listing.currency,
            "price_amount": quantize_price(
                shipping_method_channel_listing.price_amount,
                shipping_method_channel_listing.currency,
            ),
        },
    )

    return json.loads(payload)[0]


def _calculate_added(
    previous_catalogue: defaultdict[str, set[str]],
    current_catalogue: defaultdict[str, set[str]],
    key: str,
) -> list[str]:
    return list(current_catalogue[key] - previous_catalogue[key])


def _calculate_removed(
    previous_catalogue: defaultdict[str, set[str]],
    current_catalogue: defaultdict[str, set[str]],
    key: str,
) -> list[str]:
    return _calculate_added(current_catalogue, previous_catalogue, key)


@allow_writer()
@traced_payload_generator
def generate_sale_payload(
    promotion: "Promotion",
    previous_catalogue: Optional[defaultdict[str, set[str]]] = None,
    current_catalogue: Optional[defaultdict[str, set[str]]] = None,
    requestor: Optional["RequestorOrLazyObject"] = None,
):
    if previous_catalogue is None:
        previous_catalogue = defaultdict(set)
    if current_catalogue is None:
        current_catalogue = defaultdict(set)

    serializer = PayloadSerializer()

    return serializer.serialize(
        [promotion],
        fields=[],
        extra_dict_data={
            "id": graphene.Node.to_global_id("Sale", promotion.old_sale_id),
            "meta": generate_meta(requestor_data=generate_requestor(requestor)),
            "categories_added": _calculate_added(
                previous_catalogue, current_catalogue, "categories"
            ),
            "categories_removed": _calculate_removed(
                previous_catalogue, current_catalogue, "categories"
            ),
            "collections_added": _calculate_added(
                previous_catalogue, current_catalogue, "collections"
            ),
            "collections_removed": _calculate_removed(
                previous_catalogue, current_catalogue, "collections"
            ),
            "products_added": _calculate_added(
                previous_catalogue, current_catalogue, "products"
            ),
            "products_removed": _calculate_removed(
                previous_catalogue, current_catalogue, "products"
            ),
            "variants_added": _calculate_added(
                previous_catalogue, current_catalogue, "variants"
            ),
            "variants_removed": _calculate_removed(
                previous_catalogue, current_catalogue, "variants"
            ),
        },
    )


@allow_writer()
@traced_payload_generator
def generate_sale_toggle_payload(
    promotion: "Promotion",
    catalogue: defaultdict[str, set[str]],
    requestor: Optional["RequestorOrLazyObject"] = None,
):
    serializer = PayloadSerializer()

    extra_dict_data = {key: list(ids) for key, ids in catalogue.items()}
    extra_dict_data["meta"] = generate_meta(
        requestor_data=generate_requestor(requestor)
    )
    extra_dict_data["is_active"] = promotion.is_active()
    extra_dict_data["id"] = graphene.Node.to_global_id("Sale", promotion.old_sale_id)

    return serializer.serialize(
        [promotion],
        fields=[],
        extra_dict_data=extra_dict_data,
    )

@allow_writer()
@traced_payload_generator
def generate_checkout_payload(
    checkout, requestor: Optional["RequestorOrLazyObject"] = None
):
    serializer = PayloadSerializer()
    checkout_fields = (
        "last_change",
        "status",
        "email",
        "quantity",
        "currency",
        "discount_amount",
        "discount_name",
        "language_code",
    )

    checkout_price_fields = ("discount_amount",)
    quantize_price_fields(checkout, checkout_price_fields, checkout.currency)
    user_fields = ("email", "first_name", "last_name")

    lines_dict_data = serialize_checkout_lines(checkout)

    # todo use the most appropriate warehouse
    warehouse = None

    checkout_data = serializer.serialize(
        [checkout],
        fields=checkout_fields,
        pk_field_name="token",
        additional_fields={
            "channel": (lambda o: o.channel, CHANNEL_FIELDS),
            "user": (lambda c: c.user, user_fields),
            "billing_address": (lambda c: c.billing_address, ADDRESS_FIELDS),
            "shipping_address": (lambda c: c.shipping_address, ADDRESS_FIELDS),
            "warehouse_address": (
                lambda c: warehouse.address if warehouse else None,
                ADDRESS_FIELDS,
            ),
        },
        extra_dict_data={
            # Casting to list to make it json-serializable
            "shipping_method": _generate_shipping_method_payload(
                checkout.shipping_method, checkout.channel
            ),
            "lines": list(lines_dict_data),
            "meta": generate_meta(requestor_data=generate_requestor(requestor)),
            "created": checkout.created_at,
        },
    )
    return checkout_data


@allow_writer()
@traced_payload_generator
def generate_customer_payload(
    customer: "User", requestor: Optional["RequestorOrLazyObject"] = None
):
    serializer = PayloadSerializer()
    data = serializer.serialize(
        [customer],
        fields=[
            "email",
            "first_name",
            "last_name",
            "is_active",
            "date_joined",
            "language_code",
            "private_metadata",
            "metadata",
        ],
        additional_fields={
            "default_shipping_address": (
                lambda c: c.default_shipping_address,
                ADDRESS_FIELDS,
            ),
            "default_billing_address": (
                lambda c: c.default_billing_address,
                ADDRESS_FIELDS,
            ),
            "addresses": (
                lambda c: c.addresses.all(),
                ADDRESS_FIELDS,
            ),
        },
        extra_dict_data={
            "meta": generate_meta(requestor_data=generate_requestor(requestor))
        },
    )
    return data


PRODUCT_FIELDS = (
    "name",
    "description",
    "currency",
    "updated_at",
    "weight",
    "publication_date",
    "is_published",
    "private_metadata",
    "metadata",
)


def serialize_product_channel_listing_payload(channel_listings):
    serializer = PayloadSerializer()
    fields = (
        "published_at",
        "is_published",
        "visible_in_listings",
        "available_for_purchase_at",
    )
    channel_listing_payload = serializer.serialize(
        channel_listings,
        fields=fields,
        extra_dict_data={
            "channel_slug": lambda pch: pch.channel.slug,
            # deprecated in 3.3 - published_at and available_for_purchase_at
            # should be used instead
            "publication_date": lambda pch: pch.published_at,
            "available_for_purchase": lambda pch: pch.available_for_purchase_at,
        },
    )
    return channel_listing_payload


PRODUCT_VARIANT_FIELDS = (
    "sku",
    "name",
    "track_inventory",
    "private_metadata",
    "metadata",
)


@allow_writer()
@traced_payload_generator
def generate_product_variant_listings_payload(variant_channel_listings):
    serializer = PayloadSerializer()
    fields = (
        "currency",
        "price_amount",
        "cost_price_amount",
    )
    channel_listing_payload = serializer.serialize(
        variant_channel_listings,
        fields=fields,
        extra_dict_data={"channel_slug": lambda vch: vch.channel.slug},
    )
    return channel_listing_payload


@allow_writer()
@traced_payload_generator
def generate_page_payload(
    page: Page, requestor: Optional["RequestorOrLazyObject"] = None
):
    serializer = PayloadSerializer()
    page_fields = [
        "private_metadata",
        "metadata",
        "title",
        "content",
        "published_at",
        "is_published",
        "updated_at",
    ]
    page_payload = serializer.serialize(
        [page],
        fields=page_fields,
        extra_dict_data={
            "data": generate_meta(requestor_data=generate_requestor(requestor)),
            # deprecated in 3.3 - published_at should be used instead
            "publication_date": page.published_at,
        },
    )
    return page_payload


@allow_writer()
@traced_payload_generator
def generate_payment_payload(
    payment_data: "PaymentData", requestor: Optional["RequestorOrLazyObject"] = None
):
    from .transport.utils import from_payment_app_id

    data = asdict(payment_data)

    data["amount"] = quantize_price(data["amount"], data["currency"])
    if payment_app_data := from_payment_app_id(data["gateway"]):
        data["payment_method"] = payment_app_data.name
        data["meta"] = generate_meta(requestor_data=generate_requestor(requestor))
    return json.dumps(data, cls=CustomJsonEncoder)


@allow_writer()
@traced_payload_generator
def generate_list_gateways_payload(
    currency: Optional[str], checkout
):
    if checkout:
        # Deserialize checkout payload to dict and generate a new payload including
        # currency.
        checkout_data = json.loads(generate_checkout_payload(checkout))[0]
    else:
        checkout_data = None
    payload = {"checkout": checkout_data, "currency": currency}
    return json.dumps(payload)


def _get_sample_object(qs: QuerySet):
    """Return random object from query."""
    random_object = qs.order_by("?").first()
    return random_object


@allow_writer()
@traced_payload_generator
def generate_sample_payload(event_name: str) -> Optional[dict]:
    checkout_events = [
        WebhookEventAsyncType.CHECKOUT_UPDATED,
        WebhookEventAsyncType.CHECKOUT_CREATED,
    ]
    pages_events = [
    ]
    user_events = [
        WebhookEventAsyncType.CUSTOMER_CREATED,
        WebhookEventAsyncType.CUSTOMER_UPDATED,
    ]

    if event_name in user_events:
        user = generate_fake_user()
        payload = generate_customer_payload(user)
    elif event_name in pages_events:
        page = _get_sample_object(Page.objects.all())
        if page:
            payload = generate_page_payload(page)
    return json.loads(payload) if payload else None


def process_translation_context(context):
    additional_id_fields = [
        ("product_id", "Product"),
        ("product_variant_id", "ProductVariant"),
        ("attribute_id", "Attribute"),
        ("page_id", "Page"),
        ("page_type_id", "PageType"),
    ]
    result = {}
    for key, type_name in additional_id_fields:
        if object_id := context.get(key, None):
            result[key] = graphene.Node.to_global_id(type_name, object_id)
        else:
            result[key] = None
    return result


@allow_writer()
@traced_payload_generator
def generate_translation_payload(
    translation: "Translation", requestor: Optional["RequestorOrLazyObject"] = None
):
    object_type, object_id = translation.get_translated_object_id()
    translated_keys = [
        {"key": key, "value": value}
        for key, value in translation.get_translated_keys().items()
    ]

    context = None
    if isinstance(translation, AttributeValueTranslation):
        context = process_translation_context(translation.get_translation_context())

    translation_data = {
        "id": graphene.Node.to_global_id(object_type, object_id),
        "language_code": translation.language_code,
        "type": object_type,
        "keys": translated_keys,
        "meta": generate_meta(requestor_data=generate_requestor(requestor)),
    }

    if context:
        translation_data.update(context)

    return json.dumps(translation_data)


@allow_writer()
@traced_payload_generator
def generate_transaction_action_request_payload(
    transaction_data: "TransactionActionData",
    requestor: Optional["RequestorOrLazyObject"] = None,
) -> str:
    transaction = transaction_data.transaction

    action_value = (
        quantize_price(transaction_data.action_value, transaction.currency)
        if transaction_data.action_value
        else None
    )

    order_id = transaction.order_id
    graphql_order_id = (
        graphene.Node.to_global_id("Order", order_id) if order_id else None
    )

    payload = {
        "action": {
            "type": transaction_data.action_type,
            "value": action_value,
            "currency": transaction.currency,
        },
        "transaction": {
            "type": transaction.name,
            "name": transaction.name,
            "message": transaction.message,
            "reference": transaction.psp_reference,
            "psp_reference": transaction.psp_reference,
            "available_actions": transaction.available_actions,
            "currency": transaction.currency,
            "charged_value": quantize_price(
                transaction.charged_value, transaction.currency
            ),
            "authorized_value": quantize_price(
                transaction.authorized_value, transaction.currency
            ),
            "refunded_value": quantize_price(
                transaction.refunded_value, transaction.currency
            ),
            "canceled_value": quantize_price(
                transaction.canceled_value, transaction.currency
            ),
            "order_id": graphql_order_id,
            "created_at": transaction.created_at,
            "modified_at": transaction.modified_at,
        },
        "meta": generate_meta(requestor_data=generate_requestor(requestor)),
    }
    return json.dumps(payload, cls=CustomJsonEncoder)


@allow_writer()
@traced_payload_generator
def generate_thumbnail_payload(thumbnail: Thumbnail):
    thumbnail_id = graphene.Node.to_global_id("Thumbnail", thumbnail.id)
    return json.dumps({"id": thumbnail_id})
