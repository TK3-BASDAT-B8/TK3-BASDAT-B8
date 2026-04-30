document.addEventListener("click", function (event) {
  const closeBtn = event.target.closest("[data-close-modal]");
  if (closeBtn) {
    const modalRoot = document.getElementById("modal-root");
    if (modalRoot) modalRoot.innerHTML = "";
  }
});