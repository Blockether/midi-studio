from decimal import Decimal

import pytest

from shop.orders import (
    Line,
    Order,
    discount,
    order_total_with_discount,
    subtotal,
    to_csv,
)


def test_subtotal_sums_the_lines():
    assert subtotal([Line("pen", 150, 2), Line("book", 1200)]) == 1500


def test_discount_rounds_down():
    assert discount(999, 10) == 899


def test_discount_refuses_a_bad_percent():
    with pytest.raises(ValueError):
        discount(100, 101)


def test_csv_has_a_header_and_one_row_for_each_line():
    assert to_csv([Line("pen", 150, 2)]) == "product,unit_cents,quantity,total_cents\npen,150,2,300\n"


def test_order_total_with_discount_applies_the_volume_tier():
    order = Order([Line("pen", 150, 2), Line("book", 49700)], 1500)
    total = order_total_with_discount(order)
    assert total.goods == Decimal("500.00")
    assert (total.percent, total.volume_reduction) == (5, Decimal("25.00"))
    assert total.payable == Decimal("490.00")


def test_order_total_with_discount_never_counts_the_shipping_toward_a_tier():
    total = order_total_with_discount(Order([Line("lamp", 10000)], 60000))
    assert (total.percent, total.discount) == (0, Decimal("0.00"))
    assert total.payable == Decimal("700.00")
