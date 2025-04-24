from collections.abc import Iterable
from functools import partial
from typing import Union
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models import JSONField, Q
from django.db.models.expressions import Exists, OuterRef
from django.utils import timezone
from django.utils.crypto import get_random_string

from ..app.models import App
from ..core.models import ModelWithExternalReference, ModelWithMetadata
from ..core.utils.json_serializer import CustomJsonEncoder
from ..permission.enums import AccountPermissions, BasePermissionEnum, get_permissions
from ..permission.models import Permission, PermissionsMixin, _user_has_perm
from . import CustomerEvents


class UserManager(BaseUserManager["User"]):
    def create_user(
        self, email, password=None, is_staff=False, is_active=True, **extra_fields
    ):
        """Create a user instance with the given email and password."""
        email = UserManager.normalize_email(email)
        # Google OAuth2 backend send unnecessary username field
        extra_fields.pop("username", None)

        user = self.model(
            email=email, is_active=is_active, is_staff=is_staff, **extra_fields
        )
        if password:
            user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        user = self.create_user(
            email, password, is_staff=True, is_superuser=True, **extra_fields
        )
        group, created = Group.objects.get_or_create(name="Full Access")
        if created:
            group.permissions.add(*get_permissions())
        group.user_set.add(user)  # type: ignore[attr-defined]
        return user

    def staff(self):
        return self.get_queryset().filter(is_staff=True)


class User(
    PermissionsMixin, ModelWithMetadata, AbstractBaseUser, ModelWithExternalReference
):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=256, blank=True)
    last_name = models.CharField(max_length=256, blank=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_confirmed = models.BooleanField(default=True)
    last_confirm_email_request = models.DateTimeField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    date_joined = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    last_password_reset_request = models.DateTimeField(null=True, blank=True)
    avatar = models.ImageField(upload_to="user-avatars", blank=True, null=True)
    jwt_token_key = models.CharField(
        max_length=12, default=partial(get_random_string, length=12)
    )
    language_code = models.CharField(
        max_length=35, choices=settings.LANGUAGES, default=settings.LANGUAGE_CODE
    )
    search_document = models.TextField(blank=True, default="")
    uuid = models.UUIDField(default=uuid4, unique=True)

    USERNAME_FIELD = "email"

    objects = UserManager()

    class Meta:
        ordering = ("email",)
        permissions = (
            (AccountPermissions.MANAGE_USERS.codename, "Manage customers."),
            (AccountPermissions.MANAGE_STAFF.codename, "Manage staff."),
            (AccountPermissions.IMPERSONATE_USER.codename, "Impersonate user."),
        )
        indexes = [
            *ModelWithMetadata.Meta.indexes,
            # Orders searching index
            GinIndex(
                name="order_user_search_gin",
                # `opclasses` and `fields` should be the same length
                fields=["email", "first_name", "last_name"],
                opclasses=["gin_trgm_ops"] * 3,
            ),
            # Account searching index
            GinIndex(
                name="user_search_gin",
                # `opclasses` and `fields` should be the same length
                fields=["search_document"],
                opclasses=["gin_trgm_ops"],
            ),
            GinIndex(
                name="user_p_meta_jsonb_path_idx",
                fields=["private_metadata"],
                opclasses=["jsonb_path_ops"],
            ),
            GinIndex(
                fields=["first_name"],
                name="first_name_gin",
                opclasses=["gin_trgm_ops"],
            ),
            GinIndex(
                fields=["last_name"],
                name="last_name_gin",
                opclasses=["gin_trgm_ops"],
            ),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._effective_permissions = None

    def __str__(self):
        # Override the default __str__ of AbstractUser that returns username, which may
        # lead to leaking sensitive data in logs.
        return str(self.uuid)

    @property
    def effective_permissions(self) -> models.QuerySet[Permission]:
        if self._effective_permissions is None:
            self._effective_permissions = get_permissions()
            if not self.is_superuser:
                UserPermission = User.user_permissions.through
                user_permission_queryset = UserPermission._default_manager.filter(
                    user_id=self.pk
                ).values("permission_id")

                UserGroup = User.groups.through
                GroupPermission = Group.permissions.through
                user_group_queryset = UserGroup._default_manager.filter(
                    user_id=self.pk
                ).values("group_id")
                group_permission_queryset = GroupPermission.objects.filter(
                    Exists(user_group_queryset.filter(group_id=OuterRef("group_id")))
                ).values("permission_id")

                self._effective_permissions = self._effective_permissions.filter(
                    Q(
                        Exists(
                            user_permission_queryset.filter(
                                permission_id=OuterRef("pk")
                            )
                        )
                    )
                    | Q(
                        Exists(
                            group_permission_queryset.filter(
                                permission_id=OuterRef("pk")
                            )
                        )
                    )
                )
        return self._effective_permissions

    @effective_permissions.setter
    def effective_permissions(self, value: models.QuerySet[Permission]):
        self._effective_permissions = value
        # Drop cache for authentication backend
        self._effective_permissions_cache = None

    def get_full_name(self):
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        if self.default_billing_address:
            first_name = self.default_billing_address.first_name
            last_name = self.default_billing_address.last_name
            if first_name or last_name:
                return f"{first_name} {last_name}".strip()
        return self.email

    def get_short_name(self):
        return self.email

    def has_perm(self, perm: Union[BasePermissionEnum, str], obj=None) -> bool:
        # This method is overridden to accept perm as BasePermissionEnum
        perm = perm.value if isinstance(perm, BasePermissionEnum) else perm

        # Active superusers have all permissions.
        if self.is_active and self.is_superuser and not self._effective_permissions:
            return True
        return _user_has_perm(self, perm, obj)

    def has_perms(
        self, perm_list: Iterable[Union[BasePermissionEnum, str]], obj=None
    ) -> bool:
        # This method is overridden to accept perm as BasePermissionEnum
        perm_list = [
            perm.value if isinstance(perm, BasePermissionEnum) else perm
            for perm in perm_list
        ]
        return super().has_perms(perm_list, obj)

    def can_login(self):
        return self.is_active


class GroupManager(models.Manager):
    """The manager for the auth's Group model."""

    use_in_migrations = True

    def get_by_natural_key(self, name):
        return self.get(name=name)


class Group(models.Model):
    """The system provides a way to group users.

    Groups are a generic way of categorizing users to apply permissions, or
    some other label, to those users. A user can belong to any number of
    groups.

    A user in a group automatically has all the permissions granted to that
    group. For example, if the group 'Site editors' has the permission
    can_edit_home_page, any user in that group will have that permission.

    Beyond permissions, groups are a convenient way to categorize users to
    apply some label, or extended functionality, to them. For example, you
    could create a group 'Special users', and you could write code that would
    do special things to those users -- such as giving them access to a
    members-only portion of your site, or sending them members-only email
    messages.
    """

    name = models.CharField("name", max_length=150, unique=True)
    permissions = models.ManyToManyField(
        Permission,
        verbose_name="permissions",
        blank=True,
    )
    restricted_access_to_channels = models.BooleanField(default=False)
    channels = models.ManyToManyField("channel.Channel", blank=True)

    objects = GroupManager()

    class Meta:
        verbose_name = "group"
        verbose_name_plural = "groups"

    def __str__(self):
        return self.name

    def natural_key(self):
        return (self.name,)
