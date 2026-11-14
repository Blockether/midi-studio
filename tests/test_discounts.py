"""Tests for the volume discount rules of `DISCOUNT_DESIGN.md`.

One test per row of the examples table (section 4) and one per edge case
(section 5), plus the rules that those tables do not show on their own.
"""

from decimal import Decimal

import pytest

from shop.discounts import after_percent, order_total, order_total_for_lines, to_pln
from shop.orders import Line

D = Decimal


def test_row_1_below_tier_one_pays_full_goods_plus_shipping():
    total = order_total(D("499.99"), D("15.00"))
    assert (total.percent, total.discount, total.payable) == (0, D("0.00"), D("514.99"))


def test_row_2_at_tier_one_threshold_gets_five_percent():
    total = order_total(D("500.00"), D("15.00"))
    assert total.percent == 5
    assert total.volume_reduction == D("25.00")
    assert total.goods_after_discount == D("475.00")
    assert total.payable == D("490.00")


def test_row_3_rounds_the_amount_due_half_up_to_one_grosz():
    total = order_total(D("500.01"))
    assert total.goods_after_discount == D("475.01")
    assert total.volume_reduction == D("25.00")
    assert total.payable == D("475.01")


def test_row_4_in_the_middle_of_tier_one():
    total = order_total(D("600.00"), D("15.00"))
    assert (total.percent, total.volume_reduction, total.payable) == (
        5,
        D("30.00"),
        D("585.00"),
    )


def test_row_5_one_grosz_below_tier_two_stays_at_five_percent():
    total = order_total(D("1999.99"))
    assert (total.percent, total.volume_reduction, total.payable) == (
        5,
        D("100.00"),
        D("1899.99"),
    )


def test_row_6_at_tier_two_threshold_gets_ten_percent():
    total = order_total(D("2000.00"), D("20.00"))
    assert (total.percent, total.volume_reduction, total.payable) == (
        10,
        D("200.00"),
        D("1820.00"),
    )


def test_row_7_large_order_stays_in_the_top_tier():
    total = order_total(D("50000.00"))
    assert (total.percent, total.volume_reduction, total.payable) == (
        10,
        D("5000.00"),
        D("45000.00"),
    )


def test_row_8_shipping_only_order_gets_no_discount():
    total = order_total(D("0.00"), D("15.00"))
    assert (total.percent, total.discount, total.payable) == (0, D("0.00"), D("15.00"))


def test_row_9_promo_comes_first_and_the_tier_still_reads_the_gross_total():
    total = order_total(D("600.00"), D("15.00"), promo_percents=(10,))
    assert total.promo_reduction == D("60.00")
    assert total.percent == 5
    assert total.volume_reduction == D("27.00")
    assert total.goods_after_discount == D("513.00")
    assert total.payable == D("528.00")


def test_e1_order_without_lines_pays_only_the_shipping():
    total = order_total_for_lines([], D("15.00"))
    assert (total.goods, total.percent, total.payable) == (D("0.00"), 0, D("15.00"))


def test_e2_thresholds_are_inclusive():
    assert order_total(D("500.00")).percent == 5
    assert order_total(D("2000.00")).percent == 10
    assert order_total(D("499.99")).percent == 0
    assert order_total(D("1999.99")).percent == 5


def test_e3_crossing_a_threshold_lowers_the_bill():
    assert order_total(D("499.99")).payable == D("499.99")
    assert order_total(D("500.00")).payable == D("475.00")
    assert order_total(D("1999.99")).payable == D("1899.99")
    assert order_total(D("2000.00")).payable == D("1800.00")


def test_e4_shipping_is_never_reduced():
    total = order_total(D("0.00"), D("15.00"))
    assert total.shipping == D("15.00")
    assert total.payable == D("15.00")
    discounted = order_total(D("600.00"), D("15.00"))
    assert discounted.payable - discounted.goods_after_discount == D("15.00")


def test_e5_free_shipping_leaves_the_goods_discount_alone():
    total = order_total(D("600.00"), D("0.00"))
    assert (total.percent, total.payable) == (5, D("570.00"))


def test_e6_shipping_never_counts_toward_a_tier():
    total = order_total(D("100.00"), D("600.00"))
    assert (total.percent, total.discount, total.payable) == (0, D("0.00"), D("700.00"))


def test_e7_negative_goods_are_refused():
    with pytest.raises(ValueError):
        order_total(D("-0.01"))
    with pytest.raises(ValueError):
        order_total_for_lines([Line("pen", -150, 2)])
    with pytest.raises(ValueError):
        order_total(D("600.00"), D("-15.00"))


def test_e8_the_order_is_rounded_once_not_per_line():
    lines = [Line("pen", 7143) for _ in range(7)]
    assert to_pln(sum(line.total_cents for line in lines)) == D("500.01")
    assert order_total_for_lines(lines).payable == D("475.01")
    per_line = sum((after_percent(D("71.43"), 5) for _ in lines), D("0.00"))
    assert per_line == D("475.02")


def test_e9_a_promo_below_a_threshold_keeps_the_tier_of_the_gross_total():
    total = order_total(D("550.00"), promo_percents=(20,))
    assert total.percent == 5
    assert total.promo_reduction == D("110.00")
    assert total.payable == D("418.00")


def test_e10_percent_out_of_range_is_refused():
    with pytest.raises(ValueError):
        order_total(D("600.00"), promo_percents=(101,))
    with pytest.raises(ValueError):
        after_percent(D("600.00"), -1)


def test_e11_amounts_must_be_decimal_and_percents_must_be_int():
    with pytest.raises(TypeError):
        order_total(600.00)
    with pytest.raises(TypeError):
        order_total(D("600.00"), 15.00)
    with pytest.raises(TypeError):
        after_percent(D("600.00"), 5.0)


def test_e12_the_rules_carry_no_currency_of_their_own():
    total = order_total(D("600.00"), D("15.00"))
    assert not hasattr(total, "currency")
    assert total.payable == D("585.00")


def test_r2_the_tiers_do_not_stack():
    total = order_total(D("2500.00"))
    assert total.percent == 10
    assert total.payable == D("2250.00")
    stacked = after_percent(after_percent(D("2500.00"), 5), 10)
    assert stacked == D("2137.50")


def test_r8_pricing_the_same_order_twice_gives_the_same_result():
    first = order_total(D("600.00"), D("15.00"), promo_percents=(10,))
    second = order_total(first.goods, first.shipping, promo_percents=(10,))
    assert first == second
    assert order_total(first.payable).goods == first.payable


def test_lines_are_priced_from_their_groszy_subtotal():
    lines = [Line("pen", 150, 2), Line("book", 49700)]
    total = order_total_for_lines(lines, D("15.00"))
    assert total.goods == D("500.00")
    assert (total.percent, total.volume_reduction, total.payable) == (
        5,
        D("25.00"),
        D("490.00"),
    )
