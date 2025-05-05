import logging
from collections import defaultdict
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

import opentracing
from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound
from django.utils.module_loading import import_string
from graphene import Mutation
from graphql import GraphQLError
from graphql.execution import ExecutionResult

from ..channel.models import Channel
from ..core.db.connection import allow_writer
from ..core.models import EventDelivery
from ..graphql.core import ResolveInfo, SaleorContext
from .base_plugin import ExternalAccessTokens
from .models import PluginConfiguration

if TYPE_CHECKING:
    from ..account.models import Address, Group, User
    from ..app.models import App
    from ..core.middleware import Requestor
    from .base_plugin import BasePlugin

NotifyEventTypeChoice = str

logger = logging.getLogger(__name__)


class PluginsManager():
    """Base manager for handling plugins logic."""

    plugins_per_channel: dict[str, list["BasePlugin"]] = {}
    global_plugins: list["BasePlugin"] = []
    all_plugins: list["BasePlugin"] = []

    @property
    def database(self):
        return (
            settings.DATABASE_CONNECTION_REPLICA_NAME
            if self._allow_replica
            else settings.DATABASE_CONNECTION_DEFAULT_NAME
        )

    def _load_plugin(
        self,
        PluginClass: type["BasePlugin"],
        db_configs_map: dict,
        channel: Optional["Channel"] = None,
        requestor_getter=None,
        allow_replica=True,
    ) -> "BasePlugin":
        db_config = None
        if PluginClass.PLUGIN_ID in db_configs_map:
            db_config = db_configs_map[PluginClass.PLUGIN_ID]
            plugin_config = db_config.configuration
            active = db_config.active
            channel = db_config.channel
        else:
            plugin_config = PluginClass.DEFAULT_CONFIGURATION
            active = PluginClass.get_default_active()

        return PluginClass(
            configuration=plugin_config,
            active=active,
            channel=channel,
            requestor_getter=requestor_getter,
            db_config=db_config,
            allow_replica=allow_replica,
        )

    def __init__(self, plugins: list[str], requestor_getter=None, allow_replica=True):
        with opentracing.global_tracer().start_active_span("PluginsManager.__init__"):
            self.plugins = plugins
            self._allow_replica = allow_replica
            self.all_plugins = []
            self.global_plugins = []
            self.plugins_per_channel = defaultdict(list)
            self.loaded_all_channels = False
            self.loaded_channels: set[str] = set()
            self.loaded_global = False
            self.requestor_getter = requestor_getter

    def __del__(self) -> None:
        # remove references to plugins
        self.all_plugins.clear()
        self.global_plugins.clear()
        for c in self.plugins_per_channel.values():
            c.clear()
        self.loaded_channels.clear()

    def _ensure_channel_plugins_loaded(
        self, channel_slug: Optional[str], channel: Optional[Channel] = None
    ):
        if channel_slug is None and not self.loaded_global:
            global_db_config = self._get_db_plugin_configs(None)

            for plugin_path in self.plugins:
                with opentracing.global_tracer().start_active_span(f"{plugin_path}"):
                    PluginClass = import_string(plugin_path)
                    if not getattr(PluginClass, "CONFIGURATION_PER_CHANNEL", False):
                        plugin = self._load_plugin(
                            PluginClass,
                            global_db_config,
                            requestor_getter=self.requestor_getter,
                            allow_replica=self._allow_replica,
                        )
                        self.global_plugins.append(plugin)
                        self.all_plugins.append(plugin)
            self.loaded_global = True

        if channel_slug is not None and channel_slug not in self.loaded_channels:
            if channel is None:
                channel = (
                    Channel.objects.using(self.database)
                    .filter(slug=channel_slug)
                    .first()
                )
                if not channel:
                    return

            channel_db_config = self._get_db_plugin_configs(channel)

            for plugin_path in self.plugins:
                with opentracing.global_tracer().start_active_span(f"{plugin_path}"):
                    PluginClass = import_string(plugin_path)
                    if getattr(PluginClass, "CONFIGURATION_PER_CHANNEL", False):
                        plugin = self._load_plugin(
                            PluginClass,
                            channel_db_config,
                            channel=channel,
                            requestor_getter=self.requestor_getter,
                            allow_replica=self._allow_replica,
                        )
                        self.plugins_per_channel[channel_slug].append(plugin)
                        self.all_plugins.append(plugin)

            self._ensure_channel_plugins_loaded(None)
            self.plugins_per_channel[channel_slug].extend(self.global_plugins)
            self.loaded_channels.add(channel_slug)

    def _get_db_plugin_configs(self, channel: Optional[Channel]):
        with opentracing.global_tracer().start_active_span("_get_db_plugin_configs"):
            plugin_manager_configs = PluginConfiguration.objects.using(
                self.database
            ).filter(channel=channel)
            configs = {}
            for db_plugin_config in plugin_manager_configs.iterator():
                configs[db_plugin_config.identifier] = db_plugin_config
            return configs

    def __run_method_on_plugins(
        self,
        method_name: str,
        default_value: Any,
        *args,
        channel_slug: Optional[str],
        plugin_ids: Optional[list[str]] = None,
        **kwargs,
    ):
        """Try to run a method with the given name on each declared active plugin."""
        value = default_value
        plugins = self.get_plugins(
            channel_slug=channel_slug,
            active_only=True,
            plugin_ids=plugin_ids,
        )
        for plugin in plugins:
            value = self.__run_method_on_single_plugin(
                plugin, method_name, value, *args, **kwargs
            )
        return value

    def __run_method_on_single_plugin(
        self,
        plugin: Optional["BasePlugin"],
        method_name: str,
        previous_value: Any,
        *args,
        **kwargs,
    ) -> Any:
        """Run method_name on plugin.

        Method will return value returned from plugin's
        method. If plugin doesn't have own implementation of expected method_name, it
        will return previous_value.
        """
        plugin_method = getattr(plugin, method_name, NotImplemented)
        if plugin_method == NotImplemented:
            return previous_value
        returned_value = plugin_method(*args, **kwargs, previous_value=previous_value)  # type:ignore
        if returned_value == NotImplemented:
            return previous_value
        return returned_value

    def check_payment_balance(self, details: dict, channel_slug: str) -> dict:
        return self.__run_method_on_plugins(
            "check_payment_balance", None, details, channel_slug=channel_slug
        )

    def change_user_address(
        self,
        address: "Address",
        address_type: Optional[str],
        user: Optional["User"],
        save: bool = True,
    ) -> "Address":
        default_value = address
        return self.__run_method_on_plugins(
            "change_user_address",
            default_value,
            address,
            address_type,
            user,
            save,
            channel_slug=None,
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def customer_created(self, customer: "User"):
        default_value = None
        return self.__run_method_on_plugins(
            "customer_created", default_value, customer, channel_slug=None
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def customer_deleted(self, customer: "User", webhooks=None):
        default_value = None
        return self.__run_method_on_plugins(
            "customer_deleted",
            default_value,
            customer,
            webhooks=webhooks,
            channel_slug=None,
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def customer_updated(self, customer: "User", webhooks=None):
        default_value = None
        return self.__run_method_on_plugins(
            "customer_updated",
            default_value,
            customer,
            webhooks=webhooks,
            channel_slug=None,
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def customer_metadata_updated(self, customer: "User", webhooks=None):
        default_value = None
        return self.__run_method_on_plugins(
            "customer_metadata_updated",
            default_value,
            customer,
            webhooks=webhooks,
            channel_slug=None,
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def event_delivery_retry(self, event_delivery: "EventDelivery"):
        default_value = None
        return self.__run_method_on_plugins(
            "event_delivery_retry", default_value, event_delivery, channel_slug=None
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def permission_group_created(self, group: "Group"):
        default_value = None
        return self.__run_method_on_plugins(
            "permission_group_created", default_value, group, channel_slug=None
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def permission_group_updated(self, group: "Group"):
        default_value = None
        return self.__run_method_on_plugins(
            "permission_group_updated", default_value, group, channel_slug=None
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def permission_group_deleted(self, group: "Group"):
        default_value = None
        return self.__run_method_on_plugins(
            "permission_group_deleted", default_value, group, channel_slug=None
        )
    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def account_confirmed(self, user: "User"):
        default_value = None
        return self.__run_method_on_plugins(
            "account_confirmed", default_value, user, channel_slug=None
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def account_confirmation_requested(
        self, user: "User", channel_slug: str, token: str, redirect_url: Optional[str]
    ):
        default_value = None
        return self.__run_method_on_plugins(
            "account_confirmation_requested",
            default_value,
            user,
            channel_slug,
            token=token,
            redirect_url=redirect_url,
            channel_slug=channel_slug,
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def account_change_email_requested(
        self,
        user: "User",
        channel_slug: str,
        token: str,
        redirect_url: str,
        new_email: str,
    ):
        default_value = None
        return self.__run_method_on_plugins(
            "account_change_email_requested",
            default_value,
            user,
            channel_slug,
            token=token,
            redirect_url=redirect_url,
            new_email=new_email,
            channel_slug=channel_slug,
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def account_email_changed(
        self,
        user: "User",
    ):
        default_value = None
        return self.__run_method_on_plugins(
            "account_email_changed",
            default_value,
            user,
            channel_slug=None,
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def account_set_password_requested(
        self,
        user: "User",
        channel_slug: str,
        token: str,
        redirect_url: str,
    ):
        default_value = None
        return self.__run_method_on_plugins(
            "account_set_password_requested",
            default_value,
            user,
            channel_slug,
            token=token,
            redirect_url=redirect_url,
            channel_slug=channel_slug,
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def account_delete_requested(
        self, user: "User", channel_slug: str, token: str, redirect_url: str
    ):
        default_value = None
        return self.__run_method_on_plugins(
            "account_delete_requested",
            default_value,
            user,
            channel_slug,
            token=token,
            redirect_url=redirect_url,
            channel_slug=channel_slug,
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def account_deleted(self, user: "User"):
        default_value = None
        return self.__run_method_on_plugins(
            "account_deleted", default_value, user, channel_slug=None
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def address_created(self, address: "Address"):
        default_value = None
        return self.__run_method_on_plugins(
            "address_created", default_value, address, channel_slug=None
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def address_updated(self, address: "Address"):
        default_value = None
        return self.__run_method_on_plugins(
            "address_updated", default_value, address, channel_slug=None
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def address_deleted(self, address: "Address"):
        default_value = None
        return self.__run_method_on_plugins(
            "address_deleted", default_value, address, channel_slug=None
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def app_installed(self, app: "App"):
        default_value = None
        return self.__run_method_on_plugins(
            "app_installed", default_value, app, channel_slug=None
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def app_updated(self, app: "App"):
        default_value = None
        return self.__run_method_on_plugins(
            "app_updated", default_value, app, channel_slug=None
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def app_deleted(self, app: "App"):
        default_value = None
        return self.__run_method_on_plugins(
            "app_deleted", default_value, app, channel_slug=None
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def app_status_changed(self, app: "App"):
        default_value = None
        return self.__run_method_on_plugins(
            "app_status_changed", default_value, app, channel_slug=None
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def channel_created(self, channel: "Channel"):
        default_value = None
        return self.__run_method_on_plugins(
            "channel_created", default_value, channel, channel_slug=channel.slug
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def channel_updated(self, channel: "Channel", webhooks=None):
        default_value = None
        return self.__run_method_on_plugins(
            "channel_updated",
            default_value,
            channel,
            webhooks=webhooks,
            channel_slug=channel.slug,
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def channel_deleted(self, channel: "Channel"):
        default_value = None
        return self.__run_method_on_plugins(
            "channel_deleted", default_value, channel, channel_slug=None
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def channel_status_changed(self, channel: "Channel"):
        default_value = None
        return self.__run_method_on_plugins(
            "channel_status_changed", default_value, channel, channel_slug=channel.slug
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def channel_metadata_updated(self, channel: "Channel"):
        default_value = None
        return self.__run_method_on_plugins(
            "channel_metadata_updated",
            default_value,
            channel,
            channel_slug=channel.slug,
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def staff_created(self, staff_user: "User"):
        default_value = None
        return self.__run_method_on_plugins(
            "staff_created",
            default_value,
            staff_user,
            channel_slug=None,
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def staff_updated(self, staff_user: "User"):
        default_value = None
        return self.__run_method_on_plugins(
            "staff_updated",
            default_value,
            staff_user,
            channel_slug=None,
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def staff_deleted(self, staff_user: "User", webhooks=None):
        default_value = None
        return self.__run_method_on_plugins(
            "staff_deleted",
            default_value,
            staff_user,
            webhooks=webhooks,
            channel_slug=None,
        )

    # Note: this method is deprecated in Saleor 3.20 and will be removed in Saleor 3.21.
    # Webhook-related functionality will be moved from plugin to core modules.
    def staff_set_password_requested(
        self, user: "User", channel_slug: str, token: str, redirect_url: str
    ):
        default_value = None
        return self.__run_method_on_plugins(
            "staff_set_password_requested",
            default_value,
            user,
            channel_slug,
            token=token,
            redirect_url=redirect_url,
            channel_slug=channel_slug,
        )

    def get_all_plugins(self, active_only=False):
        if not self.loaded_all_channels:
            channels = Channel.objects.using(self.database).all()
            for channel in channels.iterator():
                self._ensure_channel_plugins_loaded(channel.slug, channel=channel)
            self.loaded_all_channels = True
        return self.get_plugins(active_only=active_only)

    def get_plugins(
        self,
        channel_slug: Optional[str] = None,
        active_only=False,
        plugin_ids: Optional[list[str]] = None,
    ) -> list["BasePlugin"]:
        """Return list of plugins for a given channel."""
        if channel_slug is not None:
            self._ensure_channel_plugins_loaded(channel_slug)
            plugins = self.plugins_per_channel[channel_slug]
        else:
            self._ensure_channel_plugins_loaded(None)
            plugins = self.all_plugins

        if active_only:
            plugins = [plugin for plugin in plugins if plugin.active]

        if plugin_ids:
            plugins = [plugin for plugin in plugins if plugin.PLUGIN_ID in plugin_ids]

        return plugins

    def list_external_authentications(self, active_only: bool = True) -> list[dict]:
        auth_basic_method = "external_obtain_access_tokens"
        plugins = self.get_plugins(active_only=active_only)
        return [
            {"id": plugin.PLUGIN_ID, "name": plugin.PLUGIN_NAME}
            for plugin in plugins
            if auth_basic_method in type(plugin).__dict__
        ]

    def _get_all_plugin_configs(self):
        with opentracing.global_tracer().start_active_span("_get_all_plugin_configs"):
            if not hasattr(self, "_plugin_configs"):
                plugin_configurations = (
                    PluginConfiguration.objects.using(self.database)
                    .prefetch_related("channel")
                    .all()
                )
                self._plugin_configs_per_channel: defaultdict[Channel, dict] = (
                    defaultdict(dict)
                )
                self._global_plugin_configs = {}
                for pc in plugin_configurations:
                    channel = pc.channel
                    if channel is None:
                        self._global_plugin_configs[pc.identifier] = pc
                    else:
                        self._plugin_configs_per_channel[channel][pc.identifier] = pc
            return self._global_plugin_configs, self._plugin_configs_per_channel

    # FIXME these methods should be more generic

    def save_plugin_configuration(
        self, plugin_id, channel_slug: Optional[str], cleaned_data: dict
    ):
        if channel_slug:
            plugins = self.get_plugins(channel_slug=channel_slug)
            channel = (
                Channel.objects.using(self.database).filter(slug=channel_slug).first()
            )
            if not channel:
                return None
        else:
            channel = None
            plugins = self.get_plugins()

        for plugin in plugins:
            if plugin.PLUGIN_ID == plugin_id:
                plugin_configuration, _ = PluginConfiguration.objects.using(
                    self.database
                ).get_or_create(
                    identifier=plugin_id,
                    channel=channel,
                    defaults={"configuration": plugin.configuration},
                )
                configuration = plugin.save_plugin_configuration(
                    plugin_configuration, cleaned_data
                )
                configuration.name = plugin.PLUGIN_NAME
                configuration.description = plugin.PLUGIN_DESCRIPTION
                plugin.active = configuration.active
                plugin.configuration = configuration.configuration
                return configuration

    def get_plugin(
        self, plugin_id: str, channel_slug: Optional[str] = None
    ) -> Optional["BasePlugin"]:
        plugins = self.get_plugins(channel_slug=channel_slug)
        for plugin in plugins:
            if plugin.check_plugin_id(plugin_id):
                return plugin
        return None

    def webhook_endpoint_without_channel(
        self, request: SaleorContext, plugin_id: str
    ) -> HttpResponse:
        # This should be removed in 3.0.0-a.25 as we want to give a possibility to have
        # no downtime between RCs
        split_path = request.path.split(plugin_id, maxsplit=1)
        path = None
        if len(split_path) == 2:
            path = split_path[1]

        default_value = HttpResponseNotFound()
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            self.get_all_plugins()
            plugin = self.get_plugin(plugin_id)

        if not plugin:
            return default_value
        return self.__run_method_on_single_plugin(
            plugin, "webhook", default_value, request, path
        )

    def webhook(
        self, request: SaleorContext, plugin_id: str, channel_slug: Optional[str]
    ) -> HttpResponse:
        split_path = request.path.split(plugin_id, maxsplit=1)
        path = None
        if len(split_path) == 2:
            path = split_path[1]

        default_value = HttpResponseNotFound()
        plugin = self.get_plugin(plugin_id, channel_slug=channel_slug)
        if not plugin:
            return default_value

        if not plugin.active:
            return default_value

        if plugin.CONFIGURATION_PER_CHANNEL and not channel_slug:
            return HttpResponseNotFound(
                "Incorrect endpoint. Use /plugins/channel/<channel_slug>/"
                f"{plugin.PLUGIN_ID}/"
            )

        return self.__run_method_on_single_plugin(
            plugin, "webhook", default_value, request, path
        )

    def notify(
        self,
        event: "NotifyEventTypeChoice",
        payload_func: Callable,
        channel_slug: Optional[str] = None,
        plugin_id: Optional[str] = None,
    ):
        default_value = None
        if plugin_id:
            plugin = self.get_plugin(plugin_id, channel_slug=channel_slug)
            return self.__run_method_on_single_plugin(
                plugin=plugin,
                method_name="notify",
                previous_value=default_value,
                event=event,
                payload_func=payload_func,
            )
        return self.__run_method_on_plugins(
            "notify", default_value, event, payload_func, channel_slug=channel_slug
        )

    def external_obtain_access_tokens(
        self, plugin_id: str, data: dict, request: SaleorContext
    ) -> ExternalAccessTokens:
        """Obtain access tokens from authentication plugin."""
        default_value = ExternalAccessTokens()
        plugin = self.get_plugin(plugin_id)
        return self.__run_method_on_single_plugin(
            plugin, "external_obtain_access_tokens", default_value, data, request
        )

    def external_authentication_url(
        self, plugin_id: str, data: dict, request: SaleorContext
    ) -> dict:
        """Handle authentication request."""
        default_value = {}  # type: ignore
        plugin = self.get_plugin(plugin_id)
        return self.__run_method_on_single_plugin(
            plugin, "external_authentication_url", default_value, data, request
        )

    def external_refresh(
        self, plugin_id: str, data: dict, request: SaleorContext
    ) -> ExternalAccessTokens:
        """Handle authentication refresh request."""
        default_value = ExternalAccessTokens()
        plugin = self.get_plugin(plugin_id)
        return self.__run_method_on_single_plugin(
            plugin, "external_refresh", default_value, data, request
        )

    def authenticate_user(self, request: SaleorContext) -> Optional["User"]:
        """Authenticate user which should be assigned to the request."""
        default_value = None
        return self.__run_method_on_plugins(
            "authenticate_user", default_value, request, channel_slug=None
        )

    def external_logout(
        self, plugin_id: str, data: dict, request: SaleorContext
    ) -> dict:
        """Logout the user."""
        default_value: dict[str, str] = {}
        plugin = self.get_plugin(plugin_id)
        return self.__run_method_on_single_plugin(
            plugin, "external_logout", default_value, data, request
        )

    def external_verify(
        self, plugin_id: str, data: dict, request: SaleorContext
    ) -> tuple[Optional["User"], dict]:
        """Verify the provided authentication data."""
        default_data: dict[str, str] = dict()
        default_user: Optional[User] = None
        default_value = default_user, default_data
        plugin = self.get_plugin(plugin_id)
        return self.__run_method_on_single_plugin(
            plugin, "external_verify", default_value, data, request
        )

    def perform_mutation(
        self, mutation_cls: Mutation, root, info: ResolveInfo, data: dict
    ) -> Optional[Union[ExecutionResult, GraphQLError]]:
        """Invoke before each mutation is executed.

        Note: This method is DEPRECATED and will be removed in Saleor 3.21.

        This allows to trigger specific logic before the mutation is executed
        but only once the permissions are checked.

        Returns one of:
            - null if the execution shall continue
            - graphql.GraphQLError
            - graphql.execution.ExecutionResult

        """
        logger.warning(
            "The manager.perform_mutation method is deprecated and will be removed in "
            "Saleor 3.21"
        )
        return self.__run_method_on_plugins(
            "perform_mutation",
            default_value=None,
            mutation_cls=mutation_cls,
            root=root,
            info=info,
            data=data,
            channel_slug=None,
        )

    def is_event_active_for_any_plugin(
        self, event: str, channel_slug: Optional[str] = None
    ) -> bool:
        self._ensure_channel_plugins_loaded(channel_slug)
        """Check if any plugin supports defined event."""
        plugins = (
            self.plugins_per_channel[channel_slug] if channel_slug else self.all_plugins
        )
        only_active_plugins = [plugin for plugin in plugins if plugin.active]
        return any([plugin.is_event_active(event) for plugin in only_active_plugins])


def get_plugins_manager(
    allow_replica: bool,
    requestor_getter: Optional[Callable[[], "Requestor"]] = None,
) -> PluginsManager:
    with opentracing.global_tracer().start_active_span("get_plugins_manager"):
        if allow_replica:
            return PluginsManager(settings.PLUGINS, requestor_getter, allow_replica)
        else:
            with allow_writer():
                return PluginsManager(settings.PLUGINS, requestor_getter, allow_replica)
