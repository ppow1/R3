(() => {
  "use strict";

  function mount() {
    if (document.getElementById("steward-authority-panel")) return;

    const detail = document.querySelector(".settings-detail");
    if (!detail) return;

    const panel = document.createElement("section");
    panel.id = "steward-authority-panel";
    panel.className = "steward-authority-panel";

    panel.innerHTML = `
      <h3>Steward Authority</h3>
      <p>Institutional grants and delegation lifecycle</p>
      <nav class="steward-authority-tabs" aria-label="Authority views">
        <button type="button" data-view="pending">Pending</button>
        <button type="button" data-view="active">Active</button>
        <button type="button" data-view="history">History</button>
      </nav>
      <div id="steward-authority-status" role="status"></div>
      <div id="steward-authority-results"></div>
    `;

    detail.appendChild(panel);

    const status = panel.querySelector("#steward-authority-status");
    const results = panel.querySelector("#steward-authority-results");

    async function load(view) {
      status.textContent = "Loading " + view + "...";
      results.replaceChildren();

      try {
        const response = await fetch(
          "/api/v1/steward-authority/" + view,
          { credentials: "same-origin", cache: "no-store" }
        );

        if (!response.ok) {
          status.textContent =
            "Authority " + view + " unavailable (" +
            response.status + "). No grants have been changed.";
          return;
        }

        const data = await response.json();
        status.textContent = view + " inventory";

        const pre = document.createElement("pre");
        pre.textContent = JSON.stringify(data, null, 2);
        results.appendChild(pre);
      } catch (error) {
        status.textContent =
          "Authority connection unavailable. No grants changed.";
      }
    }

    panel.querySelectorAll("[data-view]").forEach(button => {
      button.addEventListener("click", () => {
        load(button.dataset.view);
      });
    });

    load("pending");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
