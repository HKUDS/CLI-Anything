/* OrcaRouter settings UI.
 *
 * Two authentication choices are always visible side by side and both end at
 * the same credential. The API key never leaves the server: this page only
 * ever sees a masked form and model metadata.
 *
 * Login lifecycle: one attempt at a time, tagged with a generation id. A
 * response from an abandoned attempt cannot move the current one's state.
 * `pagehide` clears busy/hint synchronously before telling the server to
 * cancel, because the guarded cleanup of the invalidated request would refuse
 * to touch state on a back-forward-cache restore.
 */
(function () {
  "use strict";

  var state = {
    catalog: null,
    capability: "chat",
    requiredModalities: [],
    selected: "",
    loginAttempt: 0,
    loginGeneration: 0,
    loginBusy: false,
    pollTimer: null,
    oob: false
  };

  function el(id) { return document.getElementById(id); }

  function api(path, options) {
    return fetch(path, Object.assign({
      headers: { "Content-Type": "application/json" },
      cache: "no-store"
    }, options || {})).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (body) {
        if (!response.ok) {
          var message = body && body.error ? body.error : ("HTTP " + response.status);
          var error = new Error(message);
          error.status = response.status;
          throw error;
        }
        return body;
      });
    });
  }

  function notice(node, message, tone) {
    if (!node) { return; }
    if (!message) { node.hidden = true; node.textContent = ""; return; }
    node.hidden = false;
    node.textContent = message;
    node.style.borderLeftColor = tone === "error" ? "var(--error)"
      : tone === "ok" ? "var(--accent)" : "var(--warn)";
  }

  // ── authentication ────────────────────────────────────────────────────────

  function renderAuth(payload) {
    var status = el("auth-status");
    var credential = payload.credential || {};
    var configured = !!payload.authenticated;

    status.textContent = configured
      ? (credential.method === "oauth_pkce" ? "signed in (OrcaRouter - Auth)" : "key stored (OrcaRouter - API)")
      : "not authenticated";
    status.dataset.status = credential.status === "needs_reauth" ? "needs_reauth" : (configured ? "ok" : "none");

    el("auth-masked").textContent = payload.masked_key || "none";
    el("method-api-key-state").textContent = credential.method === "api_key" && configured ? "in use" : "not configured";
    el("method-api-key-state").dataset.active = String(credential.method === "api_key" && configured);
    el("method-pkce-state").textContent = credential.method === "oauth_pkce" && configured ? "connected" : "not connected";
    el("method-pkce-state").dataset.active = String(credential.method === "oauth_pkce" && configured);

    if (credential.status === "needs_reauth") {
      notice(el("auth-notice"),
        "This credential was rejected upstream and needs re-authentication. Sign in again or store a new key.",
        "error");
    }
  }

  function refreshAuth() {
    return api("/api/auth/status").then(renderAuth).catch(function () {});
  }

  function renderLogin(login) {
    state.loginAttempt = login.attempt;
    state.loginGeneration = login.generation;
    state.loginBusy = !!login.busy;
    el("auth-pkce-connect").disabled = state.loginBusy;
    el("auth-pkce-oob").disabled = state.loginBusy;
    el("auth-pkce-cancel").disabled = !state.loginBusy;
    el("auth-pkce-hint").hidden = !login.hint;
    el("auth-pkce-hint").textContent = login.hint || "";
    el("auth-pkce-code-row").hidden = !(state.loginBusy && state.oob);
    if (login.authorize_url) {
      var link = el("auth-authorize-link");
      link.href = login.authorize_url;
      link.hidden = false;
    } else {
      el("auth-authorize-link").hidden = true;
    }
    if (login.last_error) { notice(el("auth-notice"), login.last_error, "error"); }
  }

  /* Drop a status response that was in flight while the login moved on.
   * A poll issued before a cancel can land after it; without this check its
   * "still busy" payload would re-open the code field of a cancelled login. */
  function isStale(login) {
    return login.generation < state.loginGeneration;
  }

  function stopPolling() {
    if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
  }

  function pollLogin(attempt) {
    stopPolling();
    state.pollTimer = setInterval(function () {
      api("/api/auth/login").then(function (login) {
        if (isStale(login)) { return; }
        renderLogin(login);
        if (!login.busy) {
          stopPolling();
          if (login.completed) {
            notice(el("auth-notice"), "Signed in. The OrcaRouter key is stored locally.", "ok");
            refreshAuth().then(function () { loadCatalog(); });
          }
        }
      }).catch(function () { stopPolling(); });
    }, 700);
  }

  function startLogin(oob) {
    state.oob = !!oob;
    return api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ flow: oob ? "oob" : "loopback" })
    }).then(function (login) {
      renderLogin(login);
      if (login.busy) { pollLogin(login.attempt); }
    }).catch(function (error) {
      notice(el("auth-notice"), error.message, "error");
    });
  }

  function cancelLogin() {
    stopPolling();
    // Invalidate locally first, so any response already in flight is discarded.
    state.loginGeneration += 1;
    state.loginBusy = false;
    state.oob = false;
    el("auth-pkce-code-row").hidden = true;
    el("auth-pkce-hint").hidden = true;
    el("auth-pkce-connect").disabled = false;
    el("auth-pkce-oob").disabled = false;
    el("auth-pkce-cancel").disabled = true;
    return api("/api/auth/login/cancel", { method: "POST" }).then(function (login) {
      renderLogin(login);
      notice(el("auth-notice"), "Sign-in cancelled.", "warn");
    }).catch(function () {});
  }

  function submitCode() {
    var code = el("auth-pkce-code").value.trim();
    if (!code) { return; }
    api("/api/auth/login/code", { method: "POST", body: JSON.stringify({ code: code }) })
      .then(function () {
        el("auth-pkce-code").value = "";
        return refreshAuth();
      })
      .then(function () {
        notice(el("auth-notice"), "Signed in. The OrcaRouter key is stored locally.", "ok");
        return loadCatalog();
      })
      .catch(function (error) { notice(el("auth-notice"), error.message, "error"); });
  }

  function saveApiKey() {
    var value = el("auth-api-key-input").value.trim();
    if (!value) { return; }
    api("/api/auth/api-key", { method: "POST", body: JSON.stringify({ api_key: value }) })
      .then(function () {
        el("auth-api-key-input").value = "";
        notice(el("auth-notice"), "API key stored locally (mode 0600).", "ok");
        return refreshAuth();
      })
      .then(function () { return loadCatalog(); })
      .catch(function (error) { notice(el("auth-notice"), error.message, "error"); });
  }

  function clearApiKey() {
    api("/api/auth/clear", { method: "POST" }).then(function () {
      notice(el("auth-notice"), "Stored credential removed.", "warn");
      return refreshAuth();
    }).then(function () { loadCatalog(); }).catch(function () {});
  }

  // ── model selector ────────────────────────────────────────────────────────

  function currentModels() {
    if (!state.catalog) { return []; }
    var wanted = state.requiredModalities;
    return state.catalog.models.filter(function (model) {
      if (!wanted.length) { return true; }
      var declared = model.input_modalities || [];
      return wanted.every(function (modality) { return declared.indexOf(modality) !== -1; });
    });
  }

  function renderCatalog(payload) {
    var previous = state.selected;
    state.catalog = payload;

    var badge = el("catalog-source");
    badge.textContent = "catalog: " + payload.source + " (" + payload.models.length + ")";
    badge.dataset.source = payload.source;
    el("catalog-url").textContent = payload.catalog_url || "/v1/models";

    if (payload.degraded) {
      notice(el("model-notice"),
        "Live catalog unavailable — showing the verified fallback list only. " + (payload.detail || ""),
        "warn");
    } else {
      notice(el("model-notice"), "", "ok");
    }

    var models = currentModels();
    var stillValid = models.some(function (model) { return model.id === previous; });
    if (!stillValid && previous) {
      state.selected = "";
      notice(el("model-notice"),
        "The previously selected model is not compatible with the current capability and was cleared.",
        "warn");
    }
    renderList(models);
    renderTrigger();
  }

  function renderTrigger() {
    var trigger = el("model-trigger");
    trigger.disabled = !state.catalog;
    var label = el("model-trigger-label");
    label.textContent = state.selected || (state.catalog ? "Select a model" : "Loading models…");
    var model = state.selected && state.catalog
      ? state.catalog.models.filter(function (m) { return m.id === state.selected; })[0]
      : null;
    el("model-meta").textContent = model
      ? ("context " + (model.context_length || "n/a") +
         " · input " + ((model.input_modalities || []).join(", ") || "unknown") +
         (model.reasoning_efforts && model.reasoning_efforts.length
           ? " · reasoning " + model.reasoning_efforts.join("/") : ""))
      : "";
  }

  function renderList(models) {
    var query = (el("model-search").value || "").toLowerCase();
    var list = el("model-list");
    list.innerHTML = "";
    var shown = models.filter(function (model) {
      return !query || model.id.toLowerCase().indexOf(query) !== -1 ||
        (model.name || "").toLowerCase().indexOf(query) !== -1;
    });
    el("model-empty").hidden = shown.length > 0;
    shown.forEach(function (model) {
      var item = document.createElement("li");
      item.setAttribute("role", "option");
      item.setAttribute("aria-selected", String(model.id === state.selected));
      item.dataset.modelId = model.id;
      var id = document.createElement("span");
      id.className = "id";
      id.textContent = model.id;
      var mods = document.createElement("span");
      mods.className = "mods";
      mods.textContent = (model.input_modalities || []).join(", ");
      item.appendChild(id);
      item.appendChild(mods);
      item.addEventListener("click", function () {
        state.selected = model.id;
        el("model-panel").hidden = true;
        el("model-trigger").setAttribute("aria-expanded", "false");
        renderList(currentModels());
        renderTrigger();
      });
      list.appendChild(item);
    });
  }

  function openPanel(open) {
    el("model-panel").hidden = !open;
    el("model-trigger").setAttribute("aria-expanded", String(open));
    if (open) { el("model-search").focus(); }
  }

  function loadCatalog() {
    var query = state.requiredModalities.length
      ? "?capability=" + encodeURIComponent(state.capability) +
        "&modalities=" + encodeURIComponent(state.requiredModalities.join(","))
      : "?capability=" + encodeURIComponent(state.capability);
    return api("/api/models" + query).then(renderCatalog).catch(function (error) {
      notice(el("model-notice"), "Could not load the model catalog: " + error.message, "error");
    });
  }

  function setAttachments(enabled) {
    state.requiredModalities = enabled ? ["image"] : [];
    loadCatalog();
  }

  // ── wiring ────────────────────────────────────────────────────────────────

  document.addEventListener("DOMContentLoaded", function () {
    el("auth-api-key-save").addEventListener("click", saveApiKey);
    el("auth-api-key-clear").addEventListener("click", clearApiKey);
    el("auth-pkce-connect").addEventListener("click", function () { startLogin(false); });
    el("auth-pkce-oob").addEventListener("click", function () { startLogin(true); });
    el("auth-pkce-cancel").addEventListener("click", cancelLogin);
    el("auth-pkce-submit").addEventListener("click", submitCode);
    el("attach-image").addEventListener("change", function (event) {
      setAttachments(event.target.checked);
    });
    el("catalog-refresh").addEventListener("click", loadCatalog);
    el("model-trigger").addEventListener("click", function () {
      openPanel(el("model-panel").hidden);
    });
    el("model-search").addEventListener("input", function () { renderList(currentModels()); });
    document.addEventListener("click", function (event) {
      var wrap = document.querySelector(".select-wrap");
      if (wrap && !wrap.contains(event.target)) { openPanel(false); }
    });

    refreshAuth();
    loadCatalog();
    api("/api/auth/login").then(renderLogin).catch(function () {});
  });

  // Back-forward-cache safe: clear local state synchronously, then tell the
  // server to release the in-flight login.
  window.addEventListener("pagehide", function () {
    stopPolling();
    state.loginGeneration += 1;  // discard any status response still in flight
    state.loginBusy = false;
    state.oob = false;
    el("auth-pkce-hint").hidden = true;
    el("auth-pkce-hint").textContent = "";
    el("auth-pkce-code-row").hidden = true;
    el("auth-pkce-connect").disabled = false;
    el("auth-pkce-oob").disabled = false;
    el("auth-pkce-cancel").disabled = true;
    try {
      fetch("/api/auth/login/cancel", { method: "POST", keepalive: true });
    } catch (error) { /* the page is going away */ }
  });
})();
