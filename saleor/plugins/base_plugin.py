from copy import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

from django.http import HttpResponse
from django.utils.functional import SimpleLazyObject
from graphene import Mutation
from graphql import GraphQLError
from graphql.execution import ExecutionResult
from promise.promise import Promise

from ..core.models import EventDelivery
from ..graphql.core import ResolveInfo, SaleorContext
from .models import PluginConfiguration

if TYPE_CHECKING:
    from ..account.models import Group, User
    from ..app.models import App
    from ..channel.models import Channel
    from ..core.middleware import Requestor
    from ..core.utils.translations import Translation

PluginConfigurationType = list[dict]
RequestorOrLazyObject = Union[SimpleLazyObject, "Requestor"]


class ConfigurationTypeField:
    STRING = "String"
    MULTILINE = "Multiline"
    BOOLEAN = "Boolean"
    SECRET = "Secret"
    SECRET_MULTILINE = "SecretMultiline"
    PASSWORD = "Password"
    OUTPUT = "OUTPUT"
    CHOICES = [
        (STRING, "Field is a String"),
        (MULTILINE, "Field is a Multiline"),
        (BOOLEAN, "Field is a Boolean"),
        (SECRET, "Field is a Secret"),
        (PASSWORD, "Field is a Password"),
        (SECRET_MULTILINE, "Field is a Secret multiline"),
        (OUTPUT, "Field is a read only"),
    ]


@dataclass
class ExternalAccessTokens:
    token: Optional[str] = None
    refresh_token: Optional[str] = None
    csrf_token: Optional[str] = None
    user: Optional["User"] = None


class BasePlugin:
    """Abstract class for storing all methods available for any plugin.

    All methods take previous_value parameter.
    previous_value contains a value calculated by the previous plugin in the queue.
    If the plugin is first, it will use default value calculated by the manager.
    """

    PLUGIN_NAME = ""
    PLUGIN_ID = ""
    PLUGIN_DESCRIPTION = ""
    CONFIG_STRUCTURE = None

    CONFIGURATION_PER_CHANNEL = True
    DEFAULT_CONFIGURATION = []
    DEFAULT_ACTIVE = False
    HIDDEN = False

    @classmethod
    def check_plugin_id(cls, plugin_id: str) -> bool:
        """Check if given plugin_id matches with the PLUGIN_ID of this plugin."""
        return cls.PLUGIN_ID == plugin_id

    def __init__(
        self,
        *,
        configuration: PluginConfigurationType,
        active: bool,
        channel: Optional["Channel"] = None,
        requestor_getter: Optional[Callable[[], "Requestor"]] = None,
        db_config: Optional["PluginConfiguration"] = None,
        allow_replica: bool = True,
    ):
        self.configuration = self.get_plugin_configuration(configuration)
        self.active = active
        self.channel = channel
        self.requestor: Optional[RequestorOrLazyObject] = (
            SimpleLazyObject(requestor_getter) if requestor_getter else requestor_getter
        )
        self.db_config = db_config
        self.allow_replica = allow_replica

    def __del__(self) -> None:
        self.channel = None
        self.db_config = None
        self.configuration.clear()
        self.requestor = None

    def __str__(self):
        return self.PLUGIN_NAME

    # Trigger when account is confirmed by user.
    #
    # Overwrite this method if you need to trigger specific logic after an account
    # is confirmed.
    #
    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    account_confirmed: Callable[["User", None], None]

    # Trigger when account confirmation is requested.
    #
    # Overwrite this method if you need to trigger specific logic after an account
    # confirmation is requested.
    #
    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    account_confirmation_requested: Callable[
        ["User", str, str, Optional[str], None], None
    ]

    # Trigger when account change email is requested.
    #
    # Overwrite this method if you need to trigger specific logic after an account
    # change email is requested.
    #
    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    account_change_email_requested: Callable[["User", str, str, str, str, None], None]

    # Trigger when account set password is requested.
    #
    # Overwrite this method if you need to trigger specific logic after an account
    # set password is requested.
    #
    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    account_set_password_requested: Callable[["User", str, str, str, None], None]

    # Trigger when account delete is confirmed.
    #
    # Overwrite this method if you need to trigger specific logic after an account
    # delete is confirmed.
    #
    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    account_deleted: Callable[["User", None], None]

    # Trigger when account email is changed.
    #
    # Overwrite this method if you need to trigger specific logic after an account
    # email is changed.
    #
    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    account_email_changed: Callable[["User", None], None]

    # Trigger when account delete is requested.
    #
    # Overwrite this method if you need to trigger specific logic after an account
    # delete is requested.
    #
    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    account_delete_requested: Callable[["User", str, str, str, None], None]

    # Trigger when app is installed.
    #
    # Overwrite this method if you need to trigger specific logic after an app is
    # installed.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    app_installed: Callable[["App", None], None]

    # Trigger when app is deleted.
    #
    # Overwrite this method if you need to trigger specific logic after an app is
    # deleted.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    app_deleted: Callable[["App", None], None]

    # Trigger when app is updated.
    #
    # Overwrite this method if you need to trigger specific logic after an app is
    # updated.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    app_updated: Callable[["App", None], None]

    # Trigger when channel status is changed.
    #
    # Overwrite this method if you need to trigger specific logic after an app
    # status is changed.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    app_status_changed: Callable[["App", None], None]

    # Authenticate user which should be assigned to the request.
    #
    # Overwrite this method if the plugin handles authentication flow.
    authenticate_user: Callable[[SaleorContext, Optional["User"]], Union["User", None]]

    # Trigger when channel is created.
    #
    # Overwrite this method if you need to trigger specific logic after a channel is
    # created.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    channel_created: Callable[["Channel", None], None]

    # Trigger when channel is deleted.
    #
    # Overwrite this method if you need to trigger specific logic after a channel is
    # deleted.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    channel_deleted: Callable[["Channel", None], None]

    # Trigger when channel is updated.
    #
    # Overwrite this method if you need to trigger specific logic after a channel is
    # updated.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    channel_updated: Callable[["Channel", None, None], None]

    # Trigger when channel status is changed.
    #
    # Overwrite this method if you need to trigger specific logic after a channel
    # status is changed.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    channel_status_changed: Callable[["Channel", None], None]

    # Trigger when channel metadata is changed.
    #
    # Overwrite this method if you need to trigger specific logic after a channel
    # metadata is changed.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    channel_metadata_updated: Callable[["Channel", None], None]

    # Trigger when user is created.
    #
    # Overwrite this method if you need to trigger specific logic after a user is
    # created.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    customer_created: Callable[["User", Any], Any]

    # Trigger when user is deleted.
    #
    # Overwrite this method if you need to trigger specific logic after a user is
    # deleted.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    customer_deleted: Callable[["User", Any, None], Any]

    # Trigger when user is updated.
    #
    # Overwrite this method if you need to trigger specific logic after a user is
    # updated.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    customer_updated: Callable[["User", Any, None], Any]

    # Trigger when user metadata is updated.
    #
    # Overwrite this method if you need to trigger specific logic after a user
    # metadata is updated.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    customer_metadata_updated: Callable[["User", Any, None], Any]

    # Handle authentication request.
    #
    # Overwrite this method if the plugin handles authentication flow.
    external_authentication_url: Callable[[dict, SaleorContext, dict], dict]

    # Handle logout request.
    #
    # Overwrite this method if the plugin handles logout flow.
    external_logout: Callable[[dict, SaleorContext, dict], Any]

    # Handle authentication request responsible for obtaining access tokens.
    #
    # Overwrite this method if the plugin handles authentication flow.
    external_obtain_access_tokens: Callable[
        [dict, SaleorContext, ExternalAccessTokens], ExternalAccessTokens
    ]

    # Handle authentication refresh request.
    #
    # Overwrite this method if the plugin handles authentication flow and supports
    # refreshing the access.
    external_refresh: Callable[
        [dict, SaleorContext, ExternalAccessTokens], ExternalAccessTokens
    ]

    # Verify the provided authentication data.
    #
    # Overwrite this method if the plugin should validate the authentication data.
    external_verify: Callable[
        [dict, SaleorContext, tuple[Union["User", None], dict]],
        tuple[Union["User", None], dict],
    ]

    get_client_token: Callable[[Any, Any], Any]

    # Trigger when permission group is created.
    #
    # Overwrite this method if you need to trigger specific logic when a permission
    # group is created.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    permission_group_created: Callable[["Group", Any], Any]

    # Trigger when permission group type is deleted.
    #
    # Overwrite this method if you need to trigger specific logic when a permission
    # group is deleted.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    permission_group_deleted: Callable[["Group", Any], Any]

    # Trigger when permission group is updated.
    #
    # Overwrite this method if you need to trigger specific logic when a permission
    # group is updated.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    permission_group_updated: Callable[["Group", Any], Any]

    # Trigger when transaction item metadata is updated.
    #
    # Overwrite this method if you need to trigger specific logic when a transaction
    # item metadata is updated.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    translations_created: Callable[[list["Translation"], None, None], Any]

    # Trigger when transaction item metadata is updated.
    #
    # Overwrite this method if you need to trigger specific logic when a transaction
    # item metadata is updated.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    translations_updated: Callable[[list["Translation"], None, None], Any]

    # Trigger when staff user is created.
    #
    # Overwrite this method if you need to trigger specific logic after a staff user is
    # created.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    staff_created: Callable[["User", Any], Any]

    # Trigger when staff user is updated.
    #
    # Overwrite this method if you need to trigger specific logic after a staff user is
    # updated.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    staff_updated: Callable[["User", Any], Any]

    # Trigger when staff user is deleted.
    #
    # Overwrite this method if you need to trigger specific logic after a staff user is
    # deleted.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    staff_deleted: Callable[["User", Any, None], Any]

    # Trigger when setting a password for staff is requested.
    #
    # Overwrite this method if you need to trigger specific logic after set
    # password for staff is requested.
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    staff_set_password_requested: Callable[["User", str, str, str, None], None]

    # Handle received http request.
    #
    # Overwrite this method if the plugin expects the incoming requests.
    webhook: Callable[[SaleorContext, str, Any], HttpResponse]

    # Triggers retry mechanism for event delivery
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from the plugin to core modules.
    event_delivery_retry: Callable[["EventDelivery", Any], EventDelivery]

    # Invoked before each mutation is executed
    #
    # This allows to trigger specific logic before the mutation is executed
    # but only once the permissions are checked.
    #
    # Returns one of:
    #    - null if the execution shall continue
    #    - an execution result
    #    - graphql.GraphQLError
    #
    # Note: This method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    perform_mutation: Callable[
        [
            Optional[Union[ExecutionResult, GraphQLError]],  # previous value
            Mutation,  # mutation class
            Any,  # mutation root
            ResolveInfo,  # resolve info
            dict,  # mutation data
        ],
        Optional[Union[ExecutionResult, GraphQLError]],
    ]

    def token_is_required_as_payment_input(self, previous_value):
        return previous_value

    @classmethod
    def _update_config_items(
        cls, configuration_to_update: list[dict], current_config: list[dict]
    ):
        config_structure: dict = (
            cls.CONFIG_STRUCTURE if cls.CONFIG_STRUCTURE is not None else {}
        )
        configuration_to_update_dict = {
            c_field["name"]: c_field.get("value") for c_field in configuration_to_update
        }
        for config_item in current_config:
            new_value = configuration_to_update_dict.get(config_item["name"])
            if new_value is None:
                continue
            item_type = config_structure.get(config_item["name"], {}).get("type")
            new_value = cls._clean_configuration_value(item_type, new_value)
            if new_value is not None:
                config_item.update([("value", new_value)])

        # Get new keys that don't exist in current_config and extend it.
        current_config_keys = set(c_field["name"] for c_field in current_config)
        missing_keys = set(configuration_to_update_dict.keys()) - current_config_keys
        for missing_key in missing_keys:
            if not config_structure.get(missing_key):
                continue
            item_type = config_structure.get(missing_key, {}).get("type")
            new_value = cls._clean_configuration_value(
                item_type, configuration_to_update_dict[missing_key]
            )
            if new_value is None:
                continue
            current_config.append(
                {
                    "name": missing_key,
                    "value": new_value,
                }
            )

    @classmethod
    def _clean_configuration_value(cls, item_type, new_value):
        """Clean the value that is saved in plugin configuration.

        Change the string provided as boolean into the bool value.
        Return None for Output type, as it's read only field.
        """
        if (
            item_type == ConfigurationTypeField.BOOLEAN
            and new_value
            and not isinstance(new_value, bool)
        ):
            new_value = new_value.lower() == "true"
        if item_type == ConfigurationTypeField.OUTPUT:
            # OUTPUT field is read only. No need to update it
            return
        return new_value

    @classmethod
    def validate_plugin_configuration(
        cls, plugin_configuration: "PluginConfiguration", **kwargs
    ):
        """Validate if provided configuration is correct.

        Raise django.core.exceptions.ValidationError otherwise.
        """
        return

    @classmethod
    def pre_save_plugin_configuration(cls, plugin_configuration: "PluginConfiguration"):
        """Trigger before plugin configuration will be saved.

        Overwrite this method if you need to trigger specific logic before saving a
        plugin configuration.
        """

    @classmethod
    def save_plugin_configuration(
        cls, plugin_configuration: "PluginConfiguration", cleaned_data
    ):
        current_config = plugin_configuration.configuration
        configuration_to_update = cleaned_data.get("configuration")
        if configuration_to_update:
            cls._update_config_items(configuration_to_update, current_config)

        if "active" in cleaned_data:
            plugin_configuration.active = cleaned_data["active"]

        cls.validate_plugin_configuration(plugin_configuration)
        cls.pre_save_plugin_configuration(plugin_configuration)
        plugin_configuration.save()

        if plugin_configuration.configuration:
            # Let's add a translated descriptions and labels
            cls._append_config_structure(plugin_configuration.configuration)

        return plugin_configuration

    @classmethod
    def _append_config_structure(cls, configuration: PluginConfigurationType):
        """Append configuration structure to config from the database.

        Database stores "key: value" pairs, the definition of fields should be declared
        inside of the plugin. Based on this, the plugin will generate a structure of
        configuration with current values and provide access to it via API.
        """
        config_structure = getattr(cls, "CONFIG_STRUCTURE") or {}
        fields_without_structure = []
        for configuration_field in configuration:
            structure_to_add = config_structure.get(configuration_field.get("name"))
            if structure_to_add:
                configuration_field.update(structure_to_add)
            else:
                fields_without_structure.append(configuration_field)

        if fields_without_structure:
            [
                configuration.remove(field)  # type: ignore
                for field in fields_without_structure
            ]

    @classmethod
    def _update_configuration_structure(cls, configuration: PluginConfigurationType):
        updated_configuration = []
        config_structure = getattr(cls, "CONFIG_STRUCTURE") or {}
        desired_config_keys = set(config_structure.keys())
        for config_field in configuration:
            if config_field["name"] not in desired_config_keys:
                continue
            updated_configuration.append(copy(config_field))

        configured_keys = set(d["name"] for d in updated_configuration)
        missing_keys = desired_config_keys - configured_keys

        if not missing_keys:
            return updated_configuration

        default_config = cls.DEFAULT_CONFIGURATION
        if not default_config:
            return updated_configuration

        update_values = [copy(k) for k in default_config if k["name"] in missing_keys]
        if update_values:
            updated_configuration.extend(update_values)
        return updated_configuration

    @classmethod
    def get_default_active(cls):
        return cls.DEFAULT_ACTIVE

    def get_plugin_configuration(
        self, configuration: PluginConfigurationType
    ) -> PluginConfigurationType:
        if not configuration:
            configuration = []
        configuration = self._update_configuration_structure(configuration)
        if configuration:
            # Let's add a translated descriptions and labels
            self._append_config_structure(configuration)
        return configuration

    def resolve_plugin_configuration(
        self, request
    ) -> Union[PluginConfigurationType, Promise[PluginConfigurationType]]:
        # Override this function to customize resolving plugin configuration in API.
        return self.configuration

    def is_event_active(self, event: str, channel=Optional[str]):
        return hasattr(self, event)
