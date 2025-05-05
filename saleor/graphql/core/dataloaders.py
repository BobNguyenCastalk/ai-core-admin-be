from collections.abc import Iterable
from typing import Generic, TypeVar, Union

import opentracing
import opentracing.tags
from promise import Promise
from promise.dataloader import DataLoader as BaseLoader

from ...core.db.connection import allow_writer_in_context
from . import SaleorContext
from .context import get_database_connection_name

K = TypeVar("K")
R = TypeVar("R")


class DataLoader(BaseLoader, Generic[K, R]):
    context_key: str
    context: SaleorContext
    database_connection_name: str

    def __new__(cls, context: SaleorContext):
        key = cls.context_key
        if key is None:
            raise TypeError(f"Data loader {cls} does not define a context key")
        if not hasattr(context, "dataloaders"):
            context.dataloaders = {}
        if key not in context.dataloaders:
            context.dataloaders[key] = super().__new__(cls)
        loader = context.dataloaders[key]
        assert isinstance(loader, cls)
        return loader

    def __init__(self, context: SaleorContext) -> None:
        if getattr(self, "context", None) != context:
            self.context = context
            self.database_connection_name = get_database_connection_name(context)
            super().__init__()

    def batch_load_fn(  # pylint: disable=method-hidden
        self, keys: Iterable[K]
    ) -> Promise[list[R]]:
        with opentracing.global_tracer().start_active_span(
            "dataloader.batch_load"
        ) as scope:
            span = scope.span
            span.set_tag("resource.name", self.__class__.__name__)

            with allow_writer_in_context(self.context):
                results = self.batch_load(keys)

            if not isinstance(results, Promise):
                return Promise.resolve(results)
            return results

    def batch_load(self, keys: Iterable[K]) -> Union[Promise[list[R]], list[R]]:
        raise NotImplementedError()