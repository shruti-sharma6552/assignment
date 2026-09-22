"""CinePrice pricing engine.

All monetary values are `decimal.Decimal`. Floats are never used.

Calculation order (fixed, never reordered):

    1. Base amount          = ticket price x quantity
    2. Festival discount    = flat amount, floored at 0.00
    3. Member discount      = amount after festival x percentage / 100
    4. Member cap           = min(member discount, cap)
    5. Convenience fee      = fee per ticket x quantity
    6. GST                  = (discounted amount + fee) x gst rate / 100
    7. Final amount         = taxable amount + GST

Rounding policy
---------------
Every value that leaves this module is quantized to two decimal places with
ROUND_HALF_UP by `money()`. Rounding happens at exactly three points where a
non-exact value can appear -- the member discount (a percentage of an amount),
the GST amount (a percentage of an amount) and each stored subtotal. Inputs are
already exact to the paisa, so no other stage introduces rounding, and the
rounded values are the ones carried forward into later stages. This guarantees
that the invoice total is the arithmetic sum of the printed lines.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")
HUNDRED = Decimal("100")


class PricingError(ValueError):
    """Raised when a pricing input is invalid."""


def money(value) -> Decimal:
    """Return `value` as a Decimal rounded to exactly two decimal places."""
    return to_decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def to_decimal(value) -> Decimal:
    """Convert any supported input to Decimal without going through float."""
    if isinstance(value, Decimal):
        return value
    if value is None:
        return ZERO
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PricingError("Invalid pricing configuration.") from exc


def calculate_price(
    ticket_price,
    quantity,
    festival_discount=ZERO,
    membership_percentage=ZERO,
    membership_cap=None,
    convenience_fee_per_ticket=ZERO,
    gst_rate=ZERO,
) -> dict:
    """Calculate a full ticket price breakdown.

    Returns a dict of Decimal values with the keys: base_amount,
    festival_discount, member_discount, discounted_amount, convenience_fee,
    taxable_amount, gst_rate, gst_amount, final_amount.
    """
    # ---- validate inputs -------------------------------------------------
    try:
        quantity = int(quantity)
    except (TypeError, ValueError) as exc:
        raise PricingError("Please select at least one ticket.") from exc
    if quantity <= 0:
        raise PricingError("Please select at least one ticket.")

    ticket_price = to_decimal(ticket_price)
    festival_discount = to_decimal(festival_discount)
    membership_percentage = to_decimal(membership_percentage)
    convenience_fee_per_ticket = to_decimal(convenience_fee_per_ticket)
    gst_rate = to_decimal(gst_rate)

    if ticket_price < ZERO:
        raise PricingError("Invalid pricing configuration: ticket price cannot be negative.")
    if festival_discount < ZERO:
        raise PricingError("Invalid pricing configuration: discount cannot be negative.")
    if convenience_fee_per_ticket < ZERO:
        raise PricingError("Invalid pricing configuration: convenience fee cannot be negative.")
    if not (ZERO <= membership_percentage <= HUNDRED):
        raise PricingError("Invalid membership: discount must be between 0 and 100 percent.")
    if not (ZERO <= gst_rate <= HUNDRED):
        raise PricingError("Invalid pricing configuration: GST must be between 0 and 100 percent.")

    # Step 1 -- base ticket amount
    base_amount = money(ticket_price * quantity)

    # Step 2 -- flat festival discount, never below zero
    festival_discount = money(min(festival_discount, base_amount))
    amount_after_festival = money(max(ZERO, base_amount - festival_discount))

    # Step 3 -- membership percentage discount
    calculated_member_discount = money(
        amount_after_festival * membership_percentage / HUNDRED
    )

    # Step 4 -- membership discount cap
    if membership_cap is None:
        member_discount = calculated_member_discount
    else:
        member_discount = min(calculated_member_discount, money(membership_cap))
    member_discount = money(min(member_discount, amount_after_festival))

    discounted_amount = money(amount_after_festival - member_discount)

    # Step 5 -- convenience fee per ticket
    convenience_fee = money(convenience_fee_per_ticket * quantity)

    # Step 6 -- GST on discounted ticket amount plus convenience fee
    taxable_amount = money(discounted_amount + convenience_fee)
    gst_amount = money(taxable_amount * gst_rate / HUNDRED)

    # Step 7 -- final payable amount
    final_amount = money(taxable_amount + gst_amount)

    return {
        "base_amount": base_amount,
        "festival_discount": festival_discount,
        "member_discount": member_discount,
        "discounted_amount": discounted_amount,
        "convenience_fee": convenience_fee,
        "taxable_amount": taxable_amount,
        "gst_rate": money(gst_rate),
        "gst_amount": gst_amount,
        "final_amount": final_amount,
    }


def active_festival_discount(on_date=None):
    """Return the festival Discount valid on `on_date`, or None."""
    from datetime import date

    from models import Discount

    on_date = on_date or date.today()
    return (
        Discount.query.filter(
            Discount.active.is_(True),
            Discount.start_date <= on_date,
            Discount.end_date >= on_date,
        )
        .order_by(Discount.amount.desc())
        .first()
    )


def quote_for_tier(seat_tier, quantity, membership=None, on_date=None) -> dict:
    """Build a breakdown for a seat tier using live database configuration.

    The returned dict also carries the human-readable context (tier name,
    membership name, festival name) used by the breakdown and invoice pages.
    """
    from models import PricingConfig

    config = PricingConfig.get_current()
    festival = active_festival_discount(on_date)

    if membership is not None and not membership.active:
        raise PricingError("Invalid membership: this membership is no longer active.")

    surge_multiplier = Decimal("1.00")
    occupancy = Decimal(str(seat_tier.occupancy_percent))
    if occupancy >= config.surge_threshold_percent:
        surge_multiplier += (config.surge_percentage / HUNDRED)
    
    surged_price = money(seat_tier.price * surge_multiplier)

    breakdown = calculate_price(
        ticket_price=surged_price,
        quantity=quantity,
        festival_discount=festival.amount if festival else ZERO,
        membership_percentage=membership.discount_percentage if membership else ZERO,
        membership_cap=membership.discount_cap if membership else None,
        convenience_fee_per_ticket=config.convenience_fee,
        gst_rate=config.gst_rate,
    )
    breakdown["quantity"] = int(quantity)
    breakdown["ticket_price"] = surged_price
    breakdown["seat_tier_name"] = seat_tier.name
    breakdown["membership_name"] = membership.name if membership else None
    breakdown["festival_name"] = festival.name if festival else None
    return breakdown
