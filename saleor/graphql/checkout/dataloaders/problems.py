from collections import defaultdict
from collections.abc import Iterable

from promise import Promise

from ....checkout.problems import (
    CHECKOUT_LINE_PROBLEM_TYPE,
    CHECKOUT_PROBLEM_TYPE,
    get_checkout_problems,
)
from ...core.dataloaders import DataLoader



class CheckoutLinesProblemsByCheckoutIdLoader(
    DataLoader[str, dict[str, list[CHECKOUT_LINE_PROBLEM_TYPE]]]
):
    context_key = "checkout_lines_problems_by_checkout_id"


class CheckoutProblemsByCheckoutIdDataloader(
    DataLoader[str, dict[str, list[CHECKOUT_PROBLEM_TYPE]]]
):
    context_key = "checkout_problems_by_checkout_id"

    def batch_load(self, keys):
        line_problems_dataloader = CheckoutLinesProblemsByCheckoutIdLoader(self.context)

        def _resolve_problems(
            checkouts_lines_problems: list[dict[str, list[CHECKOUT_LINE_PROBLEM_TYPE]]],
        ):
            checkout_problems = defaultdict(list)
            for checkout_pk, checkout_lines_problems in zip(
                keys, checkouts_lines_problems
            ):
                checkout_problems[checkout_pk] = get_checkout_problems(
                    checkout_lines_problems
                )

            return [checkout_problems.get(key, []) for key in keys]

        return line_problems_dataloader.load_many(keys).then(_resolve_problems)
