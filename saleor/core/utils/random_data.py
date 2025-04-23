import json
import os
import unicodedata
from collections import defaultdict
from functools import lru_cache
from typing import Any, cast

from django.conf import settings
from django.core.files import File
from django.db import connection
from django.utils import timezone
from django.utils.text import slugify
from faker import Factory

from ...account.models import Group, User
from ...account.search import (
    generate_user_fields_search_document_value,
)
from ...channel.models import Channel
from ...permission.enums import (
    AccountPermissions,
    get_permissions,
)
from ...permission.models import Permission

fake = cast(Any, Factory.create())
fake.seed(0)

PRODUCTS_LIST_DIR = "products-list/"

DUMMY_STAFF_PASSWORD = "password"

DEFAULT_CURRENCY = os.environ.get("DEFAULT_CURRENCY", "USD")

IMAGES_MAPPING = {
    126: ["saleor-headless-omnichannel-book.png"],
    127: [
        "saleor-white-plimsolls-1.png",
        "saleor-white-plimsolls-2.png",
        "saleor-white-plimsolls-3.png",
        "saleor-white-plimsolls-4.png",
    ],
    128: [
        "saleor-blue-plimsolls-1.png",
        "saleor-blue-plimsolls-2.png",
        "saleor-blue-plimsolls-3.png",
        "saleor-blue-plimsolls-4.png",
    ],
    129: ["saleor-dash-force-1.png", "saleor-dash-force-2.png"],
    130: ["saleor-pauls-blanace-420-1.png", "saleor-pauls-blanace-420-2.png"],
    131: ["saleor-grey-hoodie.png"],
    132: ["saleor-blue-hoodie.png"],
    133: ["saleor-white-hoodie.png"],
    134: ["saleor-ascii-shirt-front.png", "saleor-ascii-shirt-back.png"],
    135: ["saleor-team-tee-front.png", "saleor-team-tee-front.png"],
    136: ["saleor-polo-shirt-front.png", "saleor-polo-shirt-back.png"],
    137: ["saleor-blue-polygon-tee-front.png", "saleor-blue-polygon-tee-back.png"],
    138: ["saleor-dark-polygon-tee-front.png", "saleor-dark-polygon-tee-back.png"],
    141: ["saleor-beanie-1.png", "saleor-beanie-2.png"],
    143: ["saleor-neck-warmer.png"],
    144: ["saleor-sunnies.png"],
    145: ["saleor-battle-tested-book.png"],
    146: ["saleor-enterprise-cloud-book.png"],
    147: ["saleor-own-your-stack-and-data-book.png"],
    150: ["saleor-mighty-mug.png"],
    151: ["saleor-cushion-blue.png"],
    152: ["saleor-apple-drink.png"],
    153: ["saleor-bean-drink.png"],
    154: ["saleor-banana-drink.png"],
    155: ["saleor-carrot-drink.png"],
    156: ["saleor-sunnies-dark.png"],
    157: [
        "saleor-monospace-white-tee-front.png",
        "saleor-monospace-white-tee-back.png",
    ],
    160: ["saleor-gift-100.png"],
    161: ["saleor-white-cubes-tee-front.png", "saleor-white-cubes-tee-back.png"],
    162: ["saleor-white-parrot-cushion.png"],
    163: ["saleor-gift-500.png"],
    164: ["saleor-gift-50.png"],
}

CATEGORY_IMAGES = {
    7: "accessories.jpg",
    8: "groceries.jpg",
    9: "apparel.jpg",
}

COLLECTION_IMAGES = {1: "summer.jpg", 2: "clothing.jpg", 3: "clothing.jpg"}


@lru_cache
def get_sample_data():
    path = os.path.join(
        settings.PROJECT_ROOT, "saleor", "static", "populatedb_data.json"
    )
    with open(path, encoding="utf8") as f:
        db_items = json.load(f)
    types = defaultdict(list)
    # Sort db objects by its model
    for item in db_items:
        model = item.pop("model")
        types[model].append(item)
    return types


def get_email(first_name, last_name):
    _first = unicodedata.normalize("NFD", first_name).encode("ascii", "ignore")
    _last = unicodedata.normalize("NFD", last_name).encode("ascii", "ignore")
    decoded_first = _first.lower().decode("utf-8")
    decoded_last = _last.lower().decode("utf-8")
    return f"{decoded_first}.{decoded_last}@example.com"

def create_fake_user(user_password, save=True, generate_id=False):
    first_name = fake.first_name()
    last_name = fake.last_name()
    email = get_email(first_name, last_name)

    # Skip the email if it already exists
    try:
        return User.objects.get(email=email)
    except User.DoesNotExist:
        pass

    user_params = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "is_active": True,
        "note": fake.paragraph(),
        "date_joined": fake.date_time(tzinfo=timezone.get_current_timezone()),
    }

    if generate_id:
        _, max_user_id = connection.ops.integer_field_range(
            User.id.field.get_internal_type()
        )
        user_params["id"] = fake.random_int(min=1, max=max_user_id)

    user = User(
        **user_params,
    )
    user.search_document = _prepare_search_document_value(user)

    if save:
        user.set_password(user_password)
        user.save()
    return user


def create_users(user_password, how_many=10):
    for _ in range(how_many):
        user = create_fake_user(user_password)
        yield f"User: {user.email}"


def create_permission_groups(staff_password):
    super_users = User.objects.filter(is_superuser=True)
    if not super_users:
        super_users = create_staff_users(staff_password, 1, True)
    group = create_group("Full Access", get_permissions(), super_users)
    yield f"Group: {group}"

    staff_users = create_staff_users(staff_password)
    customer_support_codenames = [
        perm.codename
        for enum in []
        for perm in enum
    ]
    customer_support_codenames.append(AccountPermissions.MANAGE_USERS.codename)
    customer_support_permissions = Permission.objects.filter(
        codename__in=customer_support_codenames
    )
    group = create_group("Customer Support", customer_support_permissions, staff_users)
    yield f"Group: {group}"


def create_staffs(staff_password):
    for permission in get_permissions():
        base_name = permission.codename.split("_")[1:]

        group_name = " ".join(base_name)
        group_name += " management"
        group_name = group_name.capitalize()

        email_base_name = [name[:-1] if name[-1] == "s" else name for name in base_name]
        user_email = ".".join(email_base_name)
        user_email += ".manager@example.com"

        user = _create_staff_user(staff_password, email=user_email)
        group = create_group(group_name, [permission], [user])

        yield f"Group: {group}"
        yield f"User: {user}"


def create_group(name, permissions, users):
    group, _ = Group.objects.get_or_create(name=name)
    group.permissions.add(*permissions)
    group.user_set.add(*users)  # type: ignore[attr-defined]
    return group


def _create_staff_user(staff_password, email=None, superuser=False):
    first_name = fake.first_name()
    last_name = fake.last_name()
    if not email:
        email = get_email(first_name, last_name)

    staff_user = User.objects.filter(email=email).first()
    if staff_user:
        return staff_user

    staff_user = User.objects.create_user(
        first_name=first_name,
        last_name=last_name,
        email=email,
        password=staff_password,
        is_staff=True,
        is_active=True,
        is_superuser=superuser,
        search_document=_prepare_search_document_value(
            User(email=email, first_name=first_name, last_name=last_name)
        ),
    )
    return staff_user


def _prepare_search_document_value(user):
    search_document_value = generate_user_fields_search_document_value(user)
    return search_document_value


def create_staff_users(staff_password, how_many=2, superuser=False):
    users = []
    for _ in range(how_many):
        staff_user = _create_staff_user(staff_password, superuser=superuser)
        users.append(staff_user)
    return users


def create_channel(channel_name, currency_code, slug=None, country=None):
    if not slug:
        slug = slugify(channel_name)
    channel, _ = Channel.objects.get_or_create(
        slug=slug,
        defaults={
            "name": channel_name,
            "currency_code": currency_code,
            "is_active": True,
            "default_country": country,
        },
    )
    return f"Channel: {channel}"


def create_channels():
    yield create_channel(
        channel_name="Channel-USD",
        currency_code="USD",
        slug=settings.DEFAULT_CHANNEL_SLUG,
        country=settings.DEFAULT_COUNTRY,
    )
    yield create_channel(
        channel_name="Channel-PLN",
        currency_code="PLN",
        slug="channel-pln",
        country="PL",
    )


def get_image(image_dir, image_name):
    img_path = os.path.join(image_dir, image_name)
    return File(open(img_path, "rb"), name=image_name)