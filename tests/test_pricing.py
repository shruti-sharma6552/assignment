"""Pricing engine tests. These exercise the service with no database."""

from decimal import Decimal

import pytest

from services.pricing_service import PricingError, calculate_price, money


def test_1_normal_booking_base_amount():
    """Gold 250 x 2 = 500.00 before discounts, fees and tax."""
    result = calculate_price(ticket_price=Decimal("250.00"), quantity=2)
    assert result["base_amount"] == Decimal("500.00")
    assert result["final_amount"] == Decimal("500.00")


def test_2_festival_discount():
    """500 - 100 = 400.00."""
    result = calculate_price(
        ticket_price=Decimal("250.00"), quantity=2,
        festival_discount=Decimal("100.00"),
    )
    assert result["festival_discount"] == Decimal("100.00")
    assert result["discounted_amount"] == Decimal("400.00")


def test_3_membership_discount_percentage():
    """10% of 500 = 50.00 when the cap is not binding."""
    result = calculate_price(
        ticket_price=Decimal("250.00"), quantity=2,
        membership_percentage=Decimal("10.00"),
        membership_cap=Decimal("500.00"),
    )
    assert result["member_discount"] == Decimal("50.00")
    assert result["discounted_amount"] == Decimal("450.00")


def test_4_membership_cap_applies():
    """10% of 650 is 65.00 but the 50.00 cap wins."""
    result = calculate_price(
        ticket_price=Decimal("250.00"), quantity=3,
        festival_discount=Decimal("100.00"),
        membership_percentage=Decimal("10.00"),
        membership_cap=Decimal("50.00"),
    )
    assert result["member_discount"] == Decimal("50.00")


def test_7_zero_quantity_is_rejected():
    with pytest.raises(PricingError):
        calculate_price(ticket_price=Decimal("250.00"), quantity=0)


def test_7b_negative_quantity_is_rejected():
    with pytest.raises(PricingError):
        calculate_price(ticket_price=Decimal("250.00"), quantity=-2)


def test_8_convenience_fee_per_ticket():
    """20.00 x 3 = 60.00."""
    result = calculate_price(
        ticket_price=Decimal("250.00"), quantity=3,
        convenience_fee_per_ticket=Decimal("20.00"),
    )
    assert result["convenience_fee"] == Decimal("60.00")


def test_9_gst_on_taxable_amount():
    """18% of 660.00 = 118.80."""
    result = calculate_price(
        ticket_price=Decimal("250.00"), quantity=3,
        festival_discount=Decimal("100.00"),
        membership_percentage=Decimal("10.00"),
        membership_cap=Decimal("50.00"),
        convenience_fee_per_ticket=Decimal("20.00"),
        gst_rate=Decimal("18.00"),
    )
    assert result["taxable_amount"] == Decimal("660.00")
    assert result["gst_amount"] == Decimal("118.80")


def test_10_complete_calculation_778_80():
    """The headline acceptance test: the total must be exactly 778.80."""
    result = calculate_price(
        ticket_price=Decimal("250.00"), quantity=3,
        festival_discount=Decimal("100.00"),
        membership_percentage=Decimal("10.00"),
        membership_cap=Decimal("50.00"),
        convenience_fee_per_ticket=Decimal("20.00"),
        gst_rate=Decimal("18.00"),
    )
    assert result == {
        "base_amount": Decimal("750.00"),
        "festival_discount": Decimal("100.00"),
        "member_discount": Decimal("50.00"),
        "discounted_amount": Decimal("600.00"),
        "convenience_fee": Decimal("60.00"),
        "taxable_amount": Decimal("660.00"),
        "gst_rate": Decimal("18.00"),
        "gst_amount": Decimal("118.80"),
        "final_amount": Decimal("778.80"),
    }
    assert str(result["final_amount"]) == "778.80"


# ---- edge cases ----------------------------------------------------------
def test_festival_discount_larger_than_base_never_goes_negative():
    result = calculate_price(
        ticket_price=Decimal("150.00"), quantity=1,
        festival_discount=Decimal("500.00"),
        convenience_fee_per_ticket=Decimal("20.00"),
        gst_rate=Decimal("18.00"),
    )
    assert result["discounted_amount"] == Decimal("0.00")
    assert result["final_amount"] == Decimal("23.60")


def test_full_membership_discount():
    result = calculate_price(
        ticket_price=Decimal("200.00"), quantity=1,
        membership_percentage=Decimal("100.00"),
        membership_cap=Decimal("1000.00"),
    )
    assert result["member_discount"] == Decimal("200.00")
    assert result["final_amount"] == Decimal("0.00")


def test_zero_gst_and_zero_fee():
    result = calculate_price(
        ticket_price=Decimal("150.00"), quantity=2,
        gst_rate=Decimal("0.00"), convenience_fee_per_ticket=Decimal("0.00"),
    )
    assert result["gst_amount"] == Decimal("0.00")
    assert result["final_amount"] == Decimal("300.00")


def test_small_amount_rounds_half_up():
    """0.125 rounds up to 0.13, never down."""
    assert money(Decimal("0.125")) == Decimal("0.13")
    result = calculate_price(
        ticket_price=Decimal("0.25"), quantity=1, gst_rate=Decimal("50.00")
    )
    assert result["gst_amount"] == Decimal("0.13")
    assert result["final_amount"] == Decimal("0.38")


def test_invalid_gst_rate_is_rejected():
    with pytest.raises(PricingError):
        calculate_price(
            ticket_price=Decimal("100.00"), quantity=1, gst_rate=Decimal("140.00")
        )


def test_invalid_membership_percentage_is_rejected():
    with pytest.raises(PricingError):
        calculate_price(
            ticket_price=Decimal("100.00"), quantity=1,
            membership_percentage=Decimal("120.00"),
        )


def test_every_returned_value_has_two_decimal_places():
    result = calculate_price(
        ticket_price=Decimal("199.99"), quantity=3,
        festival_discount=Decimal("49.50"),
        membership_percentage=Decimal("7.50"),
        membership_cap=Decimal("40.00"),
        convenience_fee_per_ticket=Decimal("17.25"),
        gst_rate=Decimal("18.00"),
    )
    for key, value in result.items():
        assert value.as_tuple().exponent == -2, f"{key} is not paisa-exact"
    assert result["final_amount"] == (
        result["taxable_amount"] + result["gst_amount"]
    )
