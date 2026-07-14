// Toolbar actions: print-to-PDF and copy-to-clipboard with feedback.
document.addEventListener("click", async (e) => {
  const btn = e.target.closest(".btn[data-action]");
  if (!btn) return;

  if (btn.dataset.action === "print") {
    window.print();
    return;
  }

  if (btn.dataset.action === "copy") {
    try {
      await navigator.clipboard.writeText(btn.dataset.copy);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = btn.dataset.copy;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
    }
    const original = btn.textContent;
    btn.textContent = "✓ Copied";
    btn.classList.add("copied");
    setTimeout(() => {
      btn.textContent = original;
      btn.classList.remove("copied");
    }, 1600);
  }
});

// When the mind map is wider than the viewport, start scrolled to its center.
document.querySelectorAll(".map-wrap").forEach((wrap) => {
  wrap.scrollLeft = (wrap.scrollWidth - wrap.clientWidth) / 2;
});

// Highlight the current section in the left "On this page" nav while scrolling.
const tocLinks = document.querySelectorAll(".page-toc a[href^='#']");
if (tocLinks.length && "IntersectionObserver" in window) {
  const byId = new Map(
    [...tocLinks].map((a) => [decodeURIComponent(a.hash.slice(1)), a])
  );
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        const link = byId.get(entry.target.id);
        if (link && entry.isIntersecting) {
          tocLinks.forEach((a) => a.style.removeProperty("color"));
          link.style.color = "var(--accent)";
        }
      }
    },
    { rootMargin: "0px 0px -70% 0px" }
  );
  byId.forEach((_, id) => {
    const el = document.getElementById(id);
    if (el) observer.observe(el);
  });
}
