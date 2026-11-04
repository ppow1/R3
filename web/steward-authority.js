(() => {
  "use strict";

  const BASE = "/api/v1/steward-authority";

  function element(tag, text, parent) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = String(text);
    if (parent) parent.appendChild(node);
    return node;
  }

  function csrf() {
    const entry = document.cookie.split("; ").find(
      item => item.startsWith("r3_steward_csrf=")
    );
    return entry ? decodeURIComponent(entry.split("=").slice(1).join("=")) : "";
  }

  async function api(path, body) {
    const options = {
      credentials: "same-origin",
      cache: "no-store",
      headers: {}
    };
    if (body !== undefined) {
      options.method = "POST";
      options.headers["Content-Type"] = "application/json";
      options.headers["X-Riverview-CSRF"] = csrf();
      options.body = JSON.stringify(body);
    }
    const response = await fetch(BASE + path, options);
    if (!response.ok) {
      let detail = "HTTP " + response.status;
      try {
        const data = await response.json();
        if (typeof data.detail === "string") detail += ": " + data.detail;
      } catch (_) {}
      throw new Error(detail);
    }
    return response.json();
  }

  function field(form, name, label, required = true) {
    const wrap = element("label", label, form);
    const input = element("input", undefined, wrap);
    input.name = name;
    input.required = required;
    input.style.display = "block";
    return input;
  }

  function stamp(value) {
    if (value === null || value === undefined) return "No expiry";
    const number = Number(value);
    if (!Number.isFinite(number)) return "Invalid timestamp";
    return new Date(number * 1000).toLocaleString();
  }

  function mount() {
    if (document.getElementById("steward-authority-panel")) return;
    const detail = document.querySelector(".settings-detail");
    if (!detail) return;

    const panel = element("section", undefined, detail);
    panel.id = "steward-authority-panel";
    panel.className = "steward-authority-panel";

    element("h3", "Steward Authority", panel);
    element("p", "Canonical R3 Grants & Delegations", panel);

    const nav = element("nav", undefined, panel);
    nav.className = "steward-authority-tabs";

    const status = element("div", "", panel);
    status.id = "steward-authority-status";
    status.setAttribute("role", "status");

    const results = element("div", undefined, panel);
    results.id = "steward-authority-results";

    const form = element("form", undefined, panel);
    form.id = "steward-grant-request";
    element("h4", "Request scoped grant", form);

    const target = field(form, "target_principal", "Resident principal");
    const resource = field(form, "resource_ref", "Resource reference");
    const action = field(form, "action", "Action");
    const scope = field(form, "scope_ref", "Scope");
    const reason = field(form, "reason", "Reason");

    const operationLabel = element("label", "Operation", form);
    const operation = element("select", undefined, operationLabel);
    for (const value of ["read", "write"]) {
      const option = element("option", value, operation);
      option.value = value;
    }

    const expiry = field(form, "expires_at", "Expiry (optional date/time)", false);
    expiry.type = "datetime-local";

    const delegableLabel = element("label", "Allow resident delegation", form);
    const delegable = element("input", undefined, delegableLabel);
    delegable.type = "checkbox";

    const submit = element("button", "Request grant", form);
    submit.type = "submit";

    async function mutate(path, payload) {
      status.textContent = "Submitting...";
      try {
        const result = await api(path, payload);
        status.textContent = "Recorded: " + JSON.stringify(result);
        await load("pending");
      } catch (error) {
        status.textContent = "Operation failed: " + error.message;
      }
    }

    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (!csrf()) {
        status.textContent = "Sign in to obtain an R3 CSRF session.";
        return;
      }
      const payload = {
        target_principal: target.value.trim(),
        resource_ref: resource.value.trim(),
        action: action.value.trim(),
        operation: operation.value,
        scope_ref: scope.value.trim(),
        reason: reason.value.trim(),
        idempotency_key: crypto.randomUUID(),
        delegable: delegable.checked,
        expires_at: expiry.value
          ? Math.floor(new Date(expiry.value).getTime() / 1000)
          : null
      };
      await mutate("/request", payload);
    });

    function renderRows(view, rows) {
      results.replaceChildren();
      if (!Array.isArray(rows)) {
        element("p", "Unexpected authority response", results);
        return;
      }
      if (!rows.length) {
        element("p", "No records", results);
        return;
      }

      for (const record of rows) {
        const section = element("section", undefined, results);
        section.className = "steward-authority-record";

        const identifier = record.request_id || record.grant_id ||
          record.event || "Authority record";

        element("strong", identifier, section);
        element("pre", JSON.stringify({
          ...record,
          expires_display: record.expires_at === undefined
            ? undefined : stamp(record.expires_at)
        }, null, 2), section);

        if (view === "pending" && record.request_id) {
          for (const [label, approve] of [
            ["Approve", true],
            ["Deny", false]
          ]) {
            const button = element("button", label, section);
            button.type = "button";
            button.addEventListener("click", async () => {
              const reason = prompt(label + " reason:");
              if (reason === null || !reason.trim()) return;
              await mutate("/decide", {
                request_id: record.request_id,
                approve,
                reason: reason.trim()
              });
            });
          }
        }

        if (view === "active" && record.grant_id) {
          const revoke = element("button", "Revoke", section);
          revoke.type = "button";
          revoke.addEventListener("click", async () => {
            const reason = prompt("Revocation reason:");
            if (reason === null || !reason.trim()) return;
            await mutate("/revoke", {
              grant_id: record.grant_id,
              reason: reason.trim()
            });
          });
        }
      }
    }

    async function load(view) {
      status.textContent = "Loading " + view + "...";
      results.replaceChildren();
      try {
        const sourceView =
          (view === "expired" || view === "revoked")
            ? "inventory" : view;
        const rows = await api("/" + sourceView);
        const now = Date.now() / 1000;
        const visible = view === "expired"
          ? rows.filter(record =>
              record.expires_at != null &&
              Number(record.expires_at) <= now)
          : view === "revoked"
            ? rows.filter(record =>
                record.revoked_at != null ||
                Number(record.active) === 0)
            : rows;
        renderRows(view, visible);
        status.textContent = view + " loaded";
      } catch (error) {
        status.textContent = "Authority unavailable: " + error.message;
      }
    }

    for (const view of [
      "pending", "active", "expired", "revoked", "history"
    ]) {
      const button = element("button", view, nav);
      button.type = "button";
      button.addEventListener("click", () => load(view));
    }

    load("pending");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
