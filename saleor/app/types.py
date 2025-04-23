class AppType:
    LOCAL = "local"
    THIRDPARTY = "thirdparty"

    CHOICES = [(LOCAL, "local"), (THIRDPARTY, "thirdparty")]


class AppExtensionMount:
    """All places where app extension can be mounted."""

    CUSTOMER_OVERVIEW_CREATE = "customer_overview_create"
    CUSTOMER_OVERVIEW_MORE_ACTIONS = "customer_overview_more_actions"
    CUSTOMER_DETAILS_MORE_ACTIONS = "customer_details_more_actions"


    NAVIGATION_CUSTOMERS = "navigation_customers"

    CHOICES = [
        (CUSTOMER_OVERVIEW_CREATE, "customer_overview_create"),
        (CUSTOMER_OVERVIEW_MORE_ACTIONS, "customer_overview_more_actions"),
        (CUSTOMER_DETAILS_MORE_ACTIONS, "customer_details_more_actions"),
        (NAVIGATION_CUSTOMERS, "navigation_customers"),
    ]


class AppExtensionTarget:
    """All available ways of opening an app extension.

    POPUP - app's extension will be mounted as a popup window
    APP_PAGE - redirect to app's page
    """

    POPUP = "popup"
    APP_PAGE = "app_page"

    CHOICES = [(POPUP, "popup"), (APP_PAGE, "app_page")]
