"""Orders and their totals."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shop.discounts import OrderTotal


@dataclass(frozen=True)
class Line:
    """One line of an order: a product, a unit price in cents and a quantity."""

    product: str
    unit_cents: int
    quantity: int = 1

    @property
    def total_cents(self) -> int:
        return self.unit_cents * self.quantity


@dataclass(frozen=True)
class Order:
    """An order: its lines and its shipping, both in cents."""

    lines: list[Line]
    shipping_cents: int = 0


def subtotal(lines: list[Line]) -> int:
    """Return the sum of the lines in cents."""
    return sum(line.total_cents for line in lines)


def discount(cents: int, percent: int) -> int:
    """Return the price after a discount of `percent`, rounded down to a cent."""
    if not 0 <= percent <= 100:
        raise ValueError("percent must be from 0 to 100")
    return cents * (100 - percent) // 100


def to_csv(lines: list[Line]) -> str:
    """Return the lines as CSV text with a header."""
    rows = ["product,unit_cents,quantity,total_cents"]
    rows += [f"{line.product},{line.unit_cents},{line.quantity},{line.total_cents}" for line in lines]
    return "\n".join(rows) + "\n"


def order_total_with_discount(order: Order) -> "OrderTotal":
    """Return the volume discounted total of `order`, with its shipping added.

    The tier is read from the goods subtotal before any discount, and the
    shipping is charged in full and never counts toward a tier. The import is
    local because `shop.discounts` prices `Line` objects from this module.
    """
    from shop.discounts import order_total_for_lines, to_pln

    return order_total_for_lines(order.lines, to_pln(order.shipping_cents))
