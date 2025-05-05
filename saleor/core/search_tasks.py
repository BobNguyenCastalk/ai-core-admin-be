from celery.utils.log import get_task_logger

from ..account.models import User
from ..account.search import prepare_user_search_document_value
from ..celeryconf import app
from .postgres import FlatConcatSearchVector

task_logger = get_task_logger(__name__)

BATCH_SIZE = 500
# Based on local testing, 500 should be a good balance between performance
# total time and memory usage. Should be tested after some time and adjusted by
# running the task on different thresholds and measure memory usage, total time
# and execution time of a single SQL statement.


@app.task
def set_user_search_document_values(updated_count: int = 0) -> None:
    users = list(
        User.objects.filter(search_document="")
        .prefetch_related("addresses")
        .order_by("-id")[:BATCH_SIZE]
    )

    if not users:
        task_logger.info("No users to update.")
        return

    updated_count += set_search_document_values(
        users, prepare_user_search_document_value
    )

    task_logger.info("Updated %d users", updated_count)

    if len(users) < BATCH_SIZE:
        task_logger.info("Setting user search document values finished.")
        return

    del users

    set_user_search_document_values.delay(updated_count)


def set_search_document_values(instances: list, prepare_search_document_func):
    if not instances:
        return 0
    Model = instances[0]._meta.model
    for instance in instances:
        instance.search_document = prepare_search_document_func(
            instance, already_prefetched=True
        )
    Model.objects.bulk_update(instances, ["search_document"])

    return len(instances)


def set_search_vector_values(
    instances,
    prepare_search_vector_func,
):
    Model = instances[0]._meta.model
    for instance in instances:
        instance.search_vector = FlatConcatSearchVector(
            *prepare_search_vector_func(instance, already_prefetched=True)
        )
    Model.objects.bulk_update(instances, ["search_vector"])

    return len(instances)
