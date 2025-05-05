import copy
import logging
from typing import TYPE_CHECKING

from faker import Faker

from ...account.models import User
from .random_data import create_fake_user

if TYPE_CHECKING:
    from ...order.models import Order

logger = logging.getLogger(__name__)

fake = Faker()


def _fake_save(*args, **kwargs):
    logger.error("Unable to save fake instance")


def generate_fake_user() -> "User":
    """Generate a fake instance of the "User" class.

    The instance cannot be saved
    """
    fake_user = create_fake_user(user_password=None, save=False, generate_id=True)
    # Prevent accidental saving of the instance
    fake_user.save = _fake_save
    return fake_user


def generate_fake_metadata() -> dict[str, str]:
    """Generate a fake metadata/private metadata dictionary."""
    return fake.pydict(value_types=str)


def anonymize_order(order: "Order") -> "Order":
    """Generate an anonymized version of the provided order.

    The instance cannot be saved
    """
    anonymized_order = copy.deepcopy(order)
    # Prevent accidental saving of the instance
    anonymized_order.save = _fake_save  # type: ignore[method-assign]
    fake_user = generate_fake_user()
    anonymized_order.user = fake_user
    anonymized_order.user_email = fake_user.email
    anonymized_order.customer_note = fake.paragraph()
    anonymized_order.metadata = generate_fake_metadata()
    anonymized_order.private_metadata = generate_fake_metadata()
    return anonymized_order