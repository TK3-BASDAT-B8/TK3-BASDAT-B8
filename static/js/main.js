function addTicketCategoryRow(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const template = container.querySelector('[data-category-row-template]');
  if (!template) return;
  const clone = template.content.cloneNode(true);
  container.appendChild(clone);
}

function removeClosestRow(button) {
  const row = button.closest('[data-row]');
  if (row) row.remove();
}

function updateTicketCreateFields() {
  const orderSelect = document.getElementById('ticket-order-select');
  const categorySelect = document.getElementById('ticket-category-select');
  const seatSelect = document.getElementById('ticket-seat-select');
  const seatWrapper = document.getElementById('ticket-seat-wrapper');
  if (!orderSelect || !categorySelect) return;

  const selectedOrder = orderSelect.options[orderSelect.selectedIndex];
  const orderEventId = selectedOrder ? selectedOrder.dataset.eventId || '' : '';

  let firstVisibleCategory = null;
  Array.from(categorySelect.options).forEach(function(opt) {
    const matchesEvent = !orderEventId || !opt.dataset.eventId || opt.dataset.eventId === orderEventId;
    const hasQuota = opt.dataset.remaining !== '0';
    opt.hidden = !matchesEvent;
    opt.disabled = !matchesEvent || !hasQuota;
    if (!firstVisibleCategory && !opt.disabled) firstVisibleCategory = opt;
  });

  if (categorySelect.selectedOptions.length && categorySelect.selectedOptions[0].disabled && firstVisibleCategory) {
    categorySelect.value = firstVisibleCategory.value;
  } else if (!categorySelect.value && firstVisibleCategory) {
    categorySelect.value = firstVisibleCategory.value;
  }

  updateSeatOptions();
}

function updateSeatOptions() {
  const categorySelect = document.getElementById('ticket-category-select');
  const seatSelect = document.getElementById('ticket-seat-select');
  const seatWrapper = document.getElementById('ticket-seat-wrapper');
  if (!categorySelect || !seatSelect || !seatWrapper) return;

  const opt = categorySelect.options[categorySelect.selectedIndex];
  const venueId = opt ? opt.dataset.venueId || '' : '';
  const reserved = opt ? opt.dataset.reserved === 'true' : false;
  seatWrapper.classList.toggle('hidden', !reserved);
  Array.from(seatSelect.options).forEach(function(seatOpt) {
    if (!seatOpt.value) {
      seatOpt.hidden = false;
      seatOpt.disabled = false;
      return;
    }
    const matchesVenue = seatOpt.dataset.venueId === venueId;
    seatOpt.hidden = !matchesVenue;
    seatOpt.disabled = !matchesVenue;
  });
  if (!reserved) seatSelect.value = '';
}

document.addEventListener('DOMContentLoaded', function() {
  const orderSelect = document.getElementById('ticket-order-select');
  const categorySelect = document.getElementById('ticket-category-select');
  if (orderSelect) orderSelect.addEventListener('change', updateTicketCreateFields);
  if (categorySelect) categorySelect.addEventListener('change', updateSeatOptions);
  updateTicketCreateFields();
});
