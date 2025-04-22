import datetime
import itertools
import json
import os
import random
import unicodedata
import uuid
from collections import defaultdict
from decimal import Decimal
from functools import lru_cache
from typing import Any, Union, cast
from unittest.mock import patch

from django.conf import settings
from django.core.files import File
from django.db import connection
from django.db.models import F
from django.utils import timezone
from django.utils.text import slugify
from faker import Factory
from faker.providers import BaseProvider
from measurement.measures import Weight
from prices import Money, TaxedMoney

from ...account.models import Address, Group, User
from ...account.search import (
    generate_address_search_document_value,
    generate_user_fields_search_document_value,
)
from ...account.utils import store_user_address
from ...attribute.models import (
    AssignedProductAttributeValue,
    AssignedVariantAttribute,
    AssignedVariantAttributeValue,
    Attribute,
    AttributePage,
    AttributeProduct,
    AttributeValue,
    AttributeVariant,
)
from ...channel.models import Channel
from ...core.weight import zero_weight
from ...menu.models import Menu, MenuItem
from ...page.models import Page, PageType
from ...permission.enums import (
    AccountPermissions,
    CheckoutPermissions,
    OrderPermissions,
    get_permissions,
)
from ...permission.models import Permission
from ...product.models import (
    Category,
    Collection,
    CollectionChannelListing,
    CollectionProduct,
    Product,
    ProductChannelListing,
    ProductMedia,
    ProductType,
    ProductVariant,
    ProductVariantChannelListing,
    VariantMedia,
)
from ...product.search import update_products_search_vector
from ..postgres import FlatConcatSearchVector

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


def get_weight(weight):
    if not weight:
        return zero_weight()
    value, unit = weight.split(":")
    return Weight(**{unit: value})


def create_product_types(product_type_data):
    for product_type in product_type_data:
        pk = product_type["pk"]
        defaults = product_type["fields"]
        defaults["weight"] = get_weight(defaults["weight"])
        ProductType.objects.update_or_create(pk=pk, defaults=defaults)


def create_categories(categories_data, placeholder_dir):
    placeholder_dir = get_product_list_images_dir(placeholder_dir)
    for category in categories_data:
        pk = category["pk"]
        defaults = category["fields"]
        parent = defaults["parent"]
        image_name = CATEGORY_IMAGES.get(pk)
        if image_name:
            background_image = get_image(placeholder_dir, image_name)
            defaults["background_image"] = background_image
        if parent:
            defaults["parent"] = Category.objects.get(pk=parent)
        Category.objects.update_or_create(pk=pk, defaults=defaults)


def create_collection_channel_listings(collection_channel_listings_data):
    channel_USD = Channel.objects.get(slug=settings.DEFAULT_CHANNEL_SLUG)
    channel_PLN = Channel.objects.get(slug="channel-pln")
    for collection_channel_listing in collection_channel_listings_data:
        pk = collection_channel_listing["pk"]
        defaults = dict(collection_channel_listing["fields"])
        defaults["collection_id"] = defaults.pop("collection")
        channel = defaults.pop("channel")
        defaults["channel_id"] = channel_USD.pk if channel == 1 else channel_PLN.pk
        CollectionChannelListing.objects.update_or_create(pk=pk, defaults=defaults)


def create_collections(data, placeholder_dir):
    placeholder_dir = get_product_list_images_dir(placeholder_dir)
    for collection in data:
        pk = collection["pk"]
        defaults = collection["fields"]
        image_name = COLLECTION_IMAGES.get(pk)
        if image_name:
            background_image = get_image(placeholder_dir, image_name)
            defaults["background_image"] = background_image
        Collection.objects.update_or_create(pk=pk, defaults=defaults)


def assign_products_to_collections(associations: list):
    for value in associations:
        pk = value["pk"]
        defaults = dict(value["fields"])
        defaults["collection_id"] = defaults.pop("collection")
        defaults["product_id"] = defaults.pop("product")
        CollectionProduct.objects.update_or_create(pk=pk, defaults=defaults)


def create_attributes(attributes_data):
    for attribute in attributes_data:
        pk = attribute["pk"]
        defaults = attribute["fields"]
        attr, _ = Attribute.objects.update_or_create(pk=pk, defaults=defaults)


def create_attributes_values(values_data):
    for value in values_data:
        pk = value["pk"]
        defaults = dict(value["fields"])
        defaults["attribute_id"] = defaults.pop("attribute")
        AttributeValue.objects.update_or_create(pk=pk, defaults=defaults)


def create_products(products_data, placeholder_dir, create_images):
    for product in products_data:
        pk = product["pk"]
        # We are skipping products without images
        if pk not in IMAGES_MAPPING:
            continue

        defaults = dict(product["fields"])
        defaults["weight"] = get_weight(defaults["weight"])
        defaults["category_id"] = defaults.pop("category")
        defaults["product_type_id"] = defaults.pop("product_type")
        if default_variant := defaults.pop("default_variant", None):
            defaults["default_variant_id"] = default_variant

        product, _ = Product.objects.update_or_create(pk=pk, defaults=defaults)

        if create_images:
            images = IMAGES_MAPPING.get(pk, [])
            for image_name in images:
                create_product_image(product, placeholder_dir, image_name)


def create_product_channel_listings(product_channel_listings_data):
    channel_USD = Channel.objects.get(slug=settings.DEFAULT_CHANNEL_SLUG)
    channel_PLN = Channel.objects.get(slug="channel-pln")
    for product_channel_listing in product_channel_listings_data:
        pk = product_channel_listing["pk"]
        defaults = dict(product_channel_listing["fields"])
        defaults["product_id"] = defaults.pop("product")
        channel = defaults.pop("channel")
        defaults["channel_id"] = channel_USD.pk if channel == 1 else channel_PLN.pk
        ProductChannelListing.objects.update_or_create(pk=pk, defaults=defaults)

def create_product_variants(variants_data, create_images):
    for variant in variants_data:
        pk = variant["pk"]
        defaults = dict(variant["fields"])
        defaults["weight"] = get_weight(defaults["weight"])
        product_id = defaults.pop("product")
        # We have not created products without images
        if product_id not in IMAGES_MAPPING:
            continue
        defaults["product_id"] = product_id
        set_field_as_money(defaults, "price_override")
        set_field_as_money(defaults, "cost_price")
        is_default_variant = defaults.pop("default", False)
        variant, _ = ProductVariant.objects.update_or_create(pk=pk, defaults=defaults)
        if is_default_variant:
            product = variant.product
            product.default_variant = variant
            product.save(update_fields=["default_variant", "updated_at"])
        if create_images:
            image = variant.product.get_first_image()
            VariantMedia.objects.get_or_create(variant=variant, media=image)
        quantity = random.randint(100, 500)


def create_product_variant_channel_listings(product_variant_channel_listings_data):
    channel_USD = Channel.objects.get(slug=settings.DEFAULT_CHANNEL_SLUG)
    channel_PLN = Channel.objects.get(slug="channel-pln")
    for variant_channel_listing in product_variant_channel_listings_data:
        pk = variant_channel_listing["pk"]
        defaults = dict(variant_channel_listing["fields"])

        defaults["variant_id"] = defaults.pop("variant")
        channel = defaults.pop("channel")
        defaults["channel_id"] = channel_USD.pk if channel == 1 else channel_PLN.pk
        ProductVariantChannelListing.objects.update_or_create(pk=pk, defaults=defaults)


def assign_attributes_to_product_types(
    association_model: Union[type[AttributeProduct], type[AttributeVariant]],
    attributes: list,
):
    for value in attributes:
        pk = value["pk"]
        defaults = dict(value["fields"])
        defaults["attribute_id"] = defaults.pop("attribute")
        defaults["product_type_id"] = defaults.pop("product_type")
        association_model.objects.update_or_create(pk=pk, defaults=defaults)


def assign_attributes_to_page_types(
    association_model: type[AttributePage],
    attributes: list,
):
    for value in attributes:
        pk = value["pk"]
        defaults = dict(value["fields"])
        defaults["attribute_id"] = defaults.pop("attribute")
        defaults["page_type_id"] = defaults.pop("page_type")
        association_model.objects.update_or_create(pk=pk, defaults=defaults)


def assign_attribute_values_to_products(values):
    for value in values:
        pk = value["pk"]
        defaults = dict(value["fields"])
        defaults["value_id"] = defaults.pop("value")
        defaults["product_id"] = defaults.pop("product")
        AssignedProductAttributeValue.objects.update_or_create(pk=pk, defaults=defaults)


def assign_attributes_to_variants(variant_attributes):
    for value in variant_attributes:
        pk = value["pk"]
        defaults = dict(value["fields"])
        defaults["variant_id"] = defaults.pop("variant")
        defaults["assignment_id"] = defaults.pop("assignment")
        AssignedVariantAttribute.objects.update_or_create(pk=pk, defaults=defaults)


def assign_attribute_values_to_variants(variant_attribute_values):
    for value in variant_attribute_values:
        pk = value["pk"]
        defaults = dict(value["fields"])
        defaults["value_id"] = defaults.pop("value")
        defaults["assignment_id"] = defaults.pop("assignment")
        AssignedVariantAttributeValue.objects.update_or_create(pk=pk, defaults=defaults)


def set_field_as_money(defaults, field):
    amount_field = f"{field}_amount"
    if amount_field in defaults and defaults[amount_field] is not None:
        defaults[field] = Money(defaults[amount_field], DEFAULT_CURRENCY)


def create_products_by_schema(placeholder_dir, create_images):
    types = get_sample_data()

    create_product_types(product_type_data=types["product.producttype"])
    create_categories(
        categories_data=types["product.category"], placeholder_dir=placeholder_dir
    )
    create_attributes(attributes_data=types["attribute.attribute"])
    create_attributes_values(values_data=types["attribute.attributevalue"])

    create_products(
        products_data=types["product.product"],
        placeholder_dir=placeholder_dir,
        create_images=create_images,
    )
    create_product_channel_listings(
        product_channel_listings_data=types["product.productchannellisting"],
    )
    create_product_variants(
        variants_data=types["product.productvariant"], create_images=create_images
    )
    create_product_variant_channel_listings(
        product_variant_channel_listings_data=types[
            "product.productvariantchannellisting"
        ],
    )
    assign_attributes_to_product_types(
        AttributeProduct, attributes=types["attribute.attributeproduct"]
    )
    assign_attributes_to_product_types(
        AttributeVariant, attributes=types["attribute.attributevariant"]
    )
    assign_attributes_to_page_types(
        AttributePage, attributes=types["attribute.attributepage"]
    )
    assign_attribute_values_to_products(
        types["attribute.assignedproductattributevalue"]
    )
    assign_attributes_to_variants(
        variant_attributes=types["attribute.assignedvariantattribute"]
    )
    assign_attribute_values_to_variants(
        types["attribute.assignedvariantattributevalue"]
    )
    create_collections(
        data=types["product.collection"], placeholder_dir=placeholder_dir
    )
    create_collection_channel_listings(
        collection_channel_listings_data=types["product.collectionchannellisting"],
    )
    assign_products_to_collections(associations=types["product.collectionproduct"])

    all_products_qs = Product.objects.all()
    update_products_search_vector(all_products_qs.values_list("id", flat=True))


class SaleorProvider(BaseProvider):
    def money(self):
        return Money(fake.pydecimal(2, 2, positive=True), DEFAULT_CURRENCY)

    def weight(self):
        return Weight(kg=fake.pydecimal(1, 2, positive=True))


fake.add_provider(SaleorProvider)


def get_email(first_name, last_name):
    _first = unicodedata.normalize("NFD", first_name).encode("ascii", "ignore")
    _last = unicodedata.normalize("NFD", last_name).encode("ascii", "ignore")
    decoded_first = _first.lower().decode("utf-8")
    decoded_last = _last.lower().decode("utf-8")
    return f"{decoded_first}.{decoded_last}@example.com"


def create_product_image(product, placeholder_dir, image_name):
    image = get_image(placeholder_dir, image_name)
    # We don't want to create duplicated product images
    if product.media.count() >= len(IMAGES_MAPPING.get(product.pk, [])):
        return None
    product_image = ProductMedia(product=product, image=image)
    product_image.save()
    return product_image


def create_address(save=True, **kwargs):
    address = Address(
        first_name=fake.first_name(),
        last_name=fake.last_name(),
        street_address_1=fake.street_address(),
        city=fake.city(),
        country=settings.DEFAULT_COUNTRY,
        **kwargs,
    )

    if address.country == "US":
        state = fake.state_abbr(include_territories=False)
        address.country_area = state
        address.postal_code = fake.postalcode_in_state(state)
    else:
        address.postal_code = fake.postalcode()

    if save:
        address.save()
    return address


def create_fake_user(user_password, save=True, generate_id=False):
    address = create_address(save=save)
    email = get_email(address.first_name, address.last_name)

    # Skip the email if it already exists
    try:
        return User.objects.get(email=email)
    except User.DoesNotExist:
        pass

    user_params = {
        "first_name": address.first_name,
        "last_name": address.last_name,
        "email": email,
        "default_billing_address": address,
        "default_shipping_address": address,
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
    user.search_document = _prepare_search_document_value(user, address)

    if save:
        user.set_password(user_password)
        user.save()
        user.addresses.add(address)
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
        for enum in [CheckoutPermissions, OrderPermissions]
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
    address = create_address()
    first_name = address.first_name
    last_name = address.last_name
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
        default_billing_address=address,
        default_shipping_address=address,
        is_staff=True,
        is_active=True,
        is_superuser=superuser,
        search_document=_prepare_search_document_value(
            User(email=email, first_name=first_name, last_name=last_name), address
        ),
    )
    staff_user.addresses.add(address)
    return staff_user


def _prepare_search_document_value(user, address):
    search_document_value = generate_user_fields_search_document_value(user)
    search_document_value += generate_address_search_document_value(address)
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

def create_page_type():
    types = get_sample_data()

    data = types["page.pagetype"]

    for page_type_data in data:
        pk = page_type_data.pop("pk")
        defaults = dict(page_type_data["fields"])
        page_type, _ = PageType.objects.update_or_create(pk=pk, defaults=defaults)
        yield f"Page type {page_type.slug} created"


def create_pages():
    types = get_sample_data()

    data_pages = types["page.page"]

    for page_data in data_pages:
        pk = page_data["pk"]
        defaults = dict(page_data["fields"])
        defaults["page_type_id"] = defaults.pop("page_type")
        page, _ = Page.objects.update_or_create(pk=pk, defaults=defaults)
        yield f"Page {page.slug} created"


def create_menus():
    types = get_sample_data()

    menu_data = types["menu.menu"]
    menu_item_data = types["menu.menuitem"]
    for menu in menu_data:
        pk = menu["pk"]
        defaults = menu["fields"]
        menu, _ = Menu.objects.update_or_create(pk=pk, defaults=defaults)
        yield f"Menu {menu.name} created"
    for menu_item in menu_item_data:
        pk = menu_item["pk"]
        defaults = dict(menu_item["fields"])
        defaults["category_id"] = defaults.pop("category")
        defaults["collection_id"] = defaults.pop("collection")
        defaults["menu_id"] = defaults.pop("menu")
        defaults["page_id"] = defaults.pop("page")
        defaults.pop("parent")
        menu_item, _ = MenuItem.objects.update_or_create(pk=pk, defaults=defaults)
        yield f"MenuItem {menu_item.name} created"
    for menu_item in menu_item_data:
        pk = menu_item["pk"]
        defaults = dict(menu_item["fields"])
        MenuItem.objects.filter(pk=pk).update(parent_id=defaults["parent"])


def get_product_list_images_dir(placeholder_dir):
    product_list_images_dir = os.path.join(placeholder_dir, PRODUCTS_LIST_DIR)
    return product_list_images_dir


def get_image(image_dir, image_name):
    img_path = os.path.join(image_dir, image_name)
    return File(open(img_path, "rb"), name=image_name)