/* CinePrice front-end helpers.
 *
 * The preview below is a convenience only. Every amount that matters is
 * recalculated by the Flask pricing service before a booking is stored.
 */
(function () {
  "use strict";

  var form = document.getElementById("ticket-form");
  if (!form) { return; }

  var config = window.CINEPRICE_CONFIG || {};
  var tierInput = document.getElementById("seat_tier_id");
  var quantityInput = document.getElementById("quantity");
  var membershipSelect = document.getElementById("membership_id");
  var continueBtn = document.getElementById("continue-btn");
  var selected = null;

  function round2(value) {
    return Math.round((value + Number.EPSILON) * 100) / 100;
  }

  function rupees(value) {
    return "₹" + round2(value).toFixed(2);
  }

  function updatePreview() {
    if (!selected) { return; }

    var quantity = parseInt(quantityInput.value, 10);
    if (isNaN(quantity) || quantity < 1) { quantity = 1; }

    var base = round2(parseFloat(selected.price) * quantity);
    var festival = Math.min(parseFloat(config.festivalDiscount || 0), base);
    var afterFestival = round2(base - festival);

    var option = membershipSelect.options[membershipSelect.selectedIndex];
    var percentage = parseFloat(option.dataset.percentage || 0);
    var cap = parseFloat(option.dataset.cap || 0);
    var member = option.value ? Math.min(round2(afterFestival * percentage / 100), cap) : 0;
    member = Math.min(member, afterFestival);

    var discounted = round2(afterFestival - member);
    var fee = round2(parseFloat(config.convenienceFee || 0) * quantity);
    var taxable = round2(discounted + fee);
    var gst = round2(taxable * parseFloat(config.gstRate || 0) / 100);
    var total = round2(taxable + gst);

    document.getElementById("pv-base").textContent = rupees(base);
    document.getElementById("pv-festival").textContent = "-" + rupees(festival);
    document.getElementById("pv-member").textContent = "-" + rupees(member);
    document.getElementById("pv-fee").textContent = rupees(fee);
    document.getElementById("pv-gst").textContent = rupees(gst);
    document.getElementById("pv-total").textContent = rupees(total);
  }

  Array.prototype.forEach.call(
    document.querySelectorAll(".cp-select-tier"),
    function (button) {
      button.addEventListener("click", function () {
        Array.prototype.forEach.call(
          document.querySelectorAll(".cp-tier"),
          function (card) { card.classList.remove("cp-tier-selected"); }
        );
        Array.prototype.forEach.call(
          document.querySelectorAll(".cp-select-tier"),
          function (other) { other.textContent = "Select"; }
        );

        selected = {
          id: button.dataset.tierId,
          price: button.dataset.price,
          available: parseInt(button.dataset.available, 10)
        };
        tierInput.value = selected.id;
        button.textContent = "Selected";
        document.getElementById("tier-card-" + selected.id).classList.add("cp-tier-selected");

        quantityInput.max = Math.min(10, selected.available);
        if (parseInt(quantityInput.value, 10) > selected.available) {
          quantityInput.value = selected.available;
        }
        continueBtn.disabled = false;
        updatePreview();
      });
    }
  );

  quantityInput.addEventListener("input", updatePreview);
  membershipSelect.addEventListener("change", updatePreview);

  form.addEventListener("submit", function (event) {
    if (!tierInput.value) {
      event.preventDefault();
      window.alert("Choose a ticket tier first.");
    }
  });
})();
