(() => {
  "use strict";
  const views = new Map([["/", "home"], ["/guest-info", "guest-info"], ["/rsvp", "rsvp"], ["/gallery", "gallery"], ["/contact", "contact"]]);
  const routes = new Map([...views].map(([path, view]) => [view, path]));
  const links = [...document.querySelectorAll("[data-view]")];
  const panels = [...document.querySelectorAll("[data-panel]")];
  function showView(view, {push = false, focus = false} = {}) {
    if (!routes.has(view)) view = "home";
    for (const panel of panels) panel.hidden = panel.dataset.panel !== view;
    for (const link of links) {
      if (link.dataset.view === view) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    }
    if (push) history.pushState({view}, "", routes.get(view));
    if (focus) { document.querySelector(".content-card")?.scrollIntoView({behavior: "smooth", block: "start"}); }
  }
  const initial = views.get(location.pathname.replace(/\/$/, "") || "/") || document.documentElement.dataset.initialView || "home";
  showView(initial);
  links.forEach((link) => link.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.shiftKey || event.metaKey || event.altKey) return;
    event.preventDefault();
    showView(link.dataset.view, {push: true, focus: true});
  }));
  window.addEventListener("popstate", () => showView(views.get(location.pathname.replace(/\/$/, "") || "/") || "home"));
  const form = document.querySelector("#rsvp-form");
  const resultBox = document.querySelector("#rsvp-status");
  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("[type=submit]");
    const payload = Object.fromEntries(new FormData(form).entries());
    payload.plus_one_requested = form.elements.plus_one_requested.checked;
    button.disabled = true;
    resultBox.className = "form-status";
    resultBox.textContent = "Sending RSVP…";
    try {
      const response = await fetch("/api/rsvp", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)});
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(data.error || "Your response could not be saved.");
      resultBox.className = "form-status success";
      resultBox.textContent = data.message || "Your response has been received.";
      form.reset();
    } catch (error) {
      resultBox.className = "form-status error";
      resultBox.textContent = error.message || "Unable to submit the RSVP.";
    } finally { button.disabled = false; }
  });
  const cards = [...document.querySelectorAll(".gallery-card")];
  const dialog = document.querySelector("#gallery-lightbox");
  const photo = document.querySelector("#lightbox-image");
  const caption = document.querySelector("#lightbox-caption");
  let current = 0;
  function show(index) {
    if (!cards.length) return;
    current = (index + cards.length) % cards.length;
    photo.src = cards[current].dataset.full;
    photo.alt = cards[current].dataset.alt || "Event photograph";
    caption.textContent = cards[current].dataset.caption || "";
  }
  cards.forEach((card, index) => card.addEventListener("click", () => {show(index); dialog.showModal();}));
  dialog?.querySelector(".lightbox-close")?.addEventListener("click", () => dialog.close());
  dialog?.querySelector(".lightbox-prev")?.addEventListener("click", () => show(current - 1));
  dialog?.querySelector(".lightbox-next")?.addEventListener("click", () => show(current + 1));
  dialog?.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
  dialog?.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft") show(current - 1);
    if (event.key === "ArrowRight") show(current + 1);
  });
})();
