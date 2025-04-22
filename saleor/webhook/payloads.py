import json
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
)

import graphene
from django.db.models import QuerySet
from django.utils import timezone
from graphene.utils.str_converters import to_camel_case

from .. import __version__
from ..account.models import User
from ..core.db.connection import allow_writer
from ..core.utils.anonymization import (
    generate_fake_user,
)
from ..page.models import Page
from . import traced_payload_generator
from .event_types import WebhookEventAsyncType
from .payload_serializers import PayloadSerializer

if TYPE_CHECKING:
    from ..plugins.base_plugin import RequestorOrLazyObject
    from ..translation.models import Translation


CHANNEL_FIELDS = ("slug")


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
        extra_dict_data={
            "meta": generate_meta(requestor_data=generate_requestor(requestor))
        },
    )
    return data


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
