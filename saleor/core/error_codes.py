from enum import Enum

class MetadataErrorCode(Enum):
    GRAPHQL_ERROR = "graphql_error"
    INVALID = "invalid"
    NOT_FOUND = "not_found"
    REQUIRED = "required"
    NOT_UPDATED = "not_updated"


class TranslationErrorCode(Enum):
    GRAPHQL_ERROR = "graphql_error"
    INVALID = "invalid"
    NOT_FOUND = "not_found"
    REQUIRED = "required"


class UploadErrorCode(Enum):
    GRAPHQL_ERROR = "graphql_error"


class CoreErrorCode(Enum):
    GRAPHQL_ERROR = "graphql_error"
