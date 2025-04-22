import graphene
from django.conf import settings

from ...account import error_codes as account_error_codes
from ...app import error_codes as app_error_codes
from ...channel import error_codes as channel_error_codes
from ...core import JobStatus, TimePeriodType
from ...core import error_codes as core_error_codes
from ...core.units import (
    AreaUnits,
    DistanceUnits,
    MeasurementUnits,
    VolumeUnits,
    WeightUnits,
)
from ...page import error_codes as page_error_codes
from ...permission.enums import get_permissions_enum_list
from ...plugins import error_codes as plugin_error_codes
from ...webhook import error_codes as webhook_error_codes
from .doc_category import (
    DOC_CATEGORY_APPS,
    DOC_CATEGORY_CHANNELS,
    DOC_CATEGORY_PAGES,
    DOC_CATEGORY_USERS,
    DOC_CATEGORY_WEBHOOKS,
)
from .utils import str_to_enum


class OrderDirection(graphene.Enum):
    ASC = ""
    DESC = "-"

    @property
    def description(self):
        # Disable all the no-member violations in this function
        # pylint: disable=no-member
        if self == OrderDirection.ASC:
            return "Specifies an ascending sort order."
        if self == OrderDirection.DESC:
            return "Specifies a descending sort order."
        raise ValueError(f"Unsupported enum value: {self.value}")


class ReportingPeriod(graphene.Enum):
    TODAY = "TODAY"
    THIS_MONTH = "THIS_MONTH"


def to_enum(enum_cls, *, type_name=None, **options) -> graphene.Enum:
    """Create a Graphene enum from a class containing a set of options.

    :param enum_cls:
        The class to build the enum from.
    :param type_name:
        The name of the type. Default is the class name + 'Enum'.
    :param options:
        - description:
            Contains the type description (default is the class's docstring)
        - deprecation_reason:
            Contains the deprecation reason.
            The default is enum_cls.__deprecation_reason__ or None.
    :return:
    """

    # note this won't work until
    # https://github.com/graphql-python/graphene/issues/956 is fixed
    deprecation_reason = getattr(enum_cls, "__deprecation_reason__", None)
    if deprecation_reason:
        options.setdefault("deprecation_reason", deprecation_reason)

    type_name = type_name or (enum_cls.__name__ + "Enum")
    enum_data = [(str_to_enum(code.upper()), code) for code, name in enum_cls.CHOICES]
    return graphene.Enum(type_name, enum_data, **options)


LanguageCodeEnum = graphene.Enum(
    "LanguageCodeEnum",
    [(lang[0].replace("-", "_").upper(), lang[0]) for lang in settings.LANGUAGES],
)


JobStatusEnum = to_enum(JobStatus)

PermissionEnum = graphene.Enum("PermissionEnum", get_permissions_enum_list())
PermissionEnum.doc_category = DOC_CATEGORY_USERS

TimePeriodTypeEnum = to_enum(TimePeriodType)

# unit enums
MeasurementUnitsEnum = to_enum(MeasurementUnits)
DistanceUnitsEnum = to_enum(DistanceUnits)
AreaUnitsEnum = to_enum(AreaUnits)
VolumeUnitsEnum = to_enum(VolumeUnits)
WeightUnitsEnum = to_enum(WeightUnits)
unit_enums = [DistanceUnitsEnum, AreaUnitsEnum, VolumeUnitsEnum, WeightUnitsEnum]


class ErrorPolicy:
    IGNORE_FAILED = "ignore_failed"
    REJECT_EVERYTHING = "reject_everything"
    REJECT_FAILED_ROWS = "reject_failed_rows"

    CHOICES = [
        (IGNORE_FAILED, "Ignore failed"),
        (REJECT_EVERYTHING, "Reject everything"),
        (REJECT_FAILED_ROWS, "Reject failed rows"),
    ]


def error_policy_enum_description(enum):
    if enum == ErrorPolicyEnum.IGNORE_FAILED:
        return (
            "Save what is possible within a single row. If there are errors in an "
            "input data row, try to save it partially and skip the invalid part."
        )
    if enum == ErrorPolicyEnum.REJECT_FAILED_ROWS:
        return "Reject rows with errors."
    if enum == ErrorPolicyEnum.REJECT_EVERYTHING:
        return "Reject all rows if there is at least one error in any of them."
    return None


ErrorPolicyEnum = to_enum(ErrorPolicy, description=error_policy_enum_description)

AccountErrorCode = graphene.Enum.from_enum(account_error_codes.AccountErrorCode)
AccountErrorCode.doc_category = DOC_CATEGORY_USERS

AppErrorCode = graphene.Enum.from_enum(app_error_codes.AppErrorCode)
AppErrorCode.doc_category = DOC_CATEGORY_APPS

ChannelErrorCode = graphene.Enum.from_enum(channel_error_codes.ChannelErrorCode)
ChannelErrorCode.doc_category = DOC_CATEGORY_CHANNELS

CustomerBulkUpdateErrorCode = graphene.Enum.from_enum(
    account_error_codes.CustomerBulkUpdateErrorCode
)
CustomerBulkUpdateErrorCode.doc_category = DOC_CATEGORY_USERS

PluginErrorCode = graphene.Enum.from_enum(plugin_error_codes.PluginErrorCode)

MetadataErrorCode = graphene.Enum.from_enum(core_error_codes.MetadataErrorCode)

PageErrorCode = graphene.Enum.from_enum(page_error_codes.PageErrorCode)
PageErrorCode.doc_category = DOC_CATEGORY_PAGES

PermissionGroupErrorCode = graphene.Enum.from_enum(
    account_error_codes.PermissionGroupErrorCode
)
PermissionGroupErrorCode.doc_category = DOC_CATEGORY_USERS

SendConfirmationEmailErrorCode = graphene.Enum.from_enum(
    account_error_codes.SendConfirmationEmailErrorCode
)
SendConfirmationEmailErrorCode.doc_category = DOC_CATEGORY_USERS

UploadErrorCode = graphene.Enum.from_enum(core_error_codes.UploadErrorCode)

TranslationErrorCode = graphene.Enum.from_enum(core_error_codes.TranslationErrorCode)

WebhookErrorCode = graphene.Enum.from_enum(webhook_error_codes.WebhookErrorCode)
WebhookErrorCode.doc_category = DOC_CATEGORY_WEBHOOKS

WebhookDryRunErrorCode = graphene.Enum.from_enum(
    webhook_error_codes.WebhookDryRunErrorCode
)
WebhookDryRunErrorCode.doc_category = DOC_CATEGORY_WEBHOOKS

WebhookTriggerErrorCode = graphene.Enum.from_enum(
    webhook_error_codes.WebhookTriggerErrorCode
)
WebhookTriggerErrorCode.doc_category = DOC_CATEGORY_WEBHOOKS
