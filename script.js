const nav = document.getElementById("nav");
const modal = document.getElementById("loginModal");
const track = document.getElementById("gamesTrack");

document.getElementById("menuBtn")?.addEventListener("click", () => {
  nav.classList.toggle("open");
});

document.querySelectorAll("[data-open='login']").forEach((btn) => {
  btn.addEventListener("click", () => { modal.hidden = false; });
});
document.querySelectorAll("[data-close]").forEach((btn) => {
  btn.addEventListener("click", () => { modal.hidden = true; });
});
modal?.addEventListener("click", (e) => {
  if (e.target === modal) modal.hidden = true;
});
document.querySelector(".sheet form")?.addEventListener("submit", (e) => {
  e.preventDefault();
  modal.hidden = true;
});
document.getElementById("prev")?.addEventListener("click", () => {
  track.scrollBy({ left: -280, behavior: "smooth" });
});
document.getElementById("next")?.addEventListener("click", () => {
  track.scrollBy({ left: 280, behavior: "smooth" });
});

if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  const live = document.querySelectorAll(".hero-art, .skills, .steps, .pricing, .logo-kid");
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      entry.target.classList.toggle("paused", !entry.isIntersecting);
    });
  }, { threshold: 0.12 });
  live.forEach((node) => io.observe(node));
}
