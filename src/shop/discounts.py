"""Volume discounts on orders: tiers on the goods, never on the shipping.

Amounts are `Decimal` PLN with two decimal places, and every reduction is
rounded half up to 0.01. The tier is chosen from the goods total before any
discount, so a promotion never costs a customer its volume tier.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from shop.orders import Line, subtotal

CENT = Decimal("0.01")
HUNDRED = Decimal(100)

TIER_ONE_THRESHOLD = Decimal("500.00")
TIER_ONE_PERCENT = 5
TIER_TWO_THRESHOLD = Decimal("2000.00")
TIER_TWO_PERCENT = 10


@dataclass(frozen=True)
class OrderTotal:
    """The price of one order: what was reduced, and what is due."""

    goods: Decimal
    promo_reduction: Decimal
    percent: int
    volume_reduction: Decimal
    shipping: Decimal
    payable: Decimal

    @property
    def discount(self) -> Decimal:
        """Return the whole reduction on the goods, without the shipping."""
        return self.promo_reduction + self.volume_reduction

    @property
    def goods_after_discount(self) -> Decimal:
        """Return the goods the customer pays for, before the shipping."""
        return self.goods - self.discount


def to_pln(groszy: int) -> Decimal:
    """Return `groszy`, the integer cents of the orders model, as PLN."""
    return (Decimal(groszy) / HUNDRED).quantize(CENT)


def _money(amount: Decimal, name: str) -> Decimal:
    """Return `amount` once it is a non-negative Decimal, or raise."""
    if not isinstance(amount, Decimal):
        raise TypeError(f"{name} must be a Decimal, not {type(amount).__name__}")
    if amount < 0:
        raise ValueError(f"{name} must not be negative, got {amount}")
    return amount


def volume_percent(goods: Decimal) -> int:
    """Return the volume tier percent for a pre-discount `goods` total.

    The thresholds are inclusive: 5 % from 500.00 PLN and 10 % from 2000.00
    PLN. Only the highest tier reached applies; the tiers never stack.
    """
    _money(goods, "goods")
    if goods >= TIER_TWO_THRESHOLD:
        return TIER_TWO_PERCENT
    if goods >= TIER_ONE_THRESHOLD:
        return TIER_ONE_PERCENT
    return 0


def after_percent(amount: Decimal, percent: int) -> Decimal:
    """Return the amount still due after `percent` off, rounded half up.

    The amount being charged is rounded once, to 0.01, and any reduction is
    the difference of two such rounded amounts.
    """
    _money(amount, "amount")
    if not isinstance(percent, int) or isinstance(percent, bool):
        raise TypeError(f"percent must be an int, not {type(percent).__name__}")
    if not 0 <= percent <= 100:
        raise ValueError("percent must be from 0 to 100")
    factor = (HUNDRED - Decimal(percent)) / HUNDRED
    return (amount * factor).quantize(CENT, rounding=ROUND_HALF_UP)


def order_total(
    goods: Decimal,
    shipping: Decimal = Decimal("0.00"),
    promo_percents: Sequence[int] = (),
) -> OrderTotal:
    """Return the `OrderTotal` for a goods total, its shipping and its promos.

    The promo percents come off the goods first, then the volume tier chosen
    from the undiscounted `goods`. The shipping is added last and is never
    reduced, and it never counts toward a tier.
    """
    _money(goods, "goods")
    _money(shipping, "shipping")
    after_promos = goods
    for percent in promo_percents:
        after_promos = after_percent(after_promos, percent)
    percent = volume_percent(goods)
    payable_goods = after_percent(after_promos, percent)
    return OrderTotal(
        goods=goods,
        promo_reduction=goods - after_promos,
        percent=percent,
        volume_reduction=after_promos - payable_goods,
        shipping=shipping,
        payable=payable_goods + shipping,
    )


def order_total_for_lines(
    lines: list[Line],
    shipping: Decimal = Decimal("0.00"),
    promo_percents: Sequence[int] = (),
) -> OrderTotal:
    """Return the `OrderTotal` for order `lines`, priced from their subtotal."""
    return order_total(to_pln(subtotal(lines)), shipping, promo_percents)
