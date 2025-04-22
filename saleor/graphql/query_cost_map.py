"""Costs map used by query complexity validator.

It's three levels deep dict of dicts:

- Type
- Fields
- Complexity

To set complexity cost for querying a field "likes" on type "User":

{
    "User": {
        "likes": {"complexity": 2}
    }
}

Querying above field will not increase query complexity by 1.

If field's complexity should be multiplied by value of argument (or arguments),
you can specify names of those arguments in "multipliers" list:

{
    "Query": {
        "products": {"complexity": 1, "multipliers": ["first", "last"]}
    }
}

This will result in following queries having cost of 100:

{ products(first: 100) { edges: { id } } }

{ products(last: 100) { edges: { id } } }

{ products(first: 10, last: 10) { edges: { id } } }

Notice that complexity is in last case is multiplied by all arguments.

Complexity is also multiplied recursively:

{
    "Query": {
        "products": {"complexity": 1, "multipliers": ["first", "last"]}
    },
    "Product": {
        "shippings": {"complexity": 1},
    }
}

This query will have cost of 200 (100 x 2 for each product):

{ products(first: 100) { complexity } }
"""

COST_MAP = {
    "Query": {
        "app": {"complexity": 1},
        "appExtension": {"complexity": 1},
        "appExtensions": {"complexity": 1, "multipliers": ["first", "last"]},
        "apps": {"complexity": 1, "multipliers": ["first", "last"]},
        "appsInstallations": {"complexity": 1},
        "me": {"complexity": 1},
        "permissionGroup": {"complexity": 1},
        "permissionGroups": {"complexity": 1, "multipliers": ["first", "last"]},
        "staffUsers": {"complexity": 1, "multipliers": ["first", "last"]},
        "translation": {"complexity": 1},
        "translations": {"complexity": 1, "multipliers": ["first", "last"]},
        "user": {"complexity": 1},
        "webhook": {"complexity": 1},
    },
    "App": {
        "extensions": {"complexity": 1},
        "tokens": {"complexity": 1},
        "webhooks": {"complexity": 1},
    },
    "Group": {
        "permissions": {"complexity": 1},
        "users": {"complexity": 1},
    },
    "User": {
        "editableGroups": {"complexity": 1},
        "events": {"complexity": 1},
        "permissionGroups": {"complexity": 1},
        "userPermissions": {"complexity": 1},
    },
}
