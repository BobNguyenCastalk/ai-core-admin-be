from django.core.management.base import BaseCommand

from ...search_tasks import (
    set_user_search_document_values,
)


class Command(BaseCommand):
    help = "Populate search indexes."

    def handle(self, *args, **options):

        # Update users
        self.stdout.write("Updating users")
        set_user_search_document_values.delay()
