/**
 * script.js - SSO Frontend JavaScript
 * Handles authentication flow, API calls, and dashboard interactions
 */

// ─────────────────────────────────────────────
// CONFIGURATION
// ─────────────────────────────────────────────
// Use server-injected API base URL (from Jinja2 template), or fallback to current origin
const API_BASE = window.API_BASE_URL || window.location.origin;

// ─────────────────────────────────────────────
// TOKEN STORAGE UTILITIES
// ─────────────────────────────────────────────

const TokenStore = {
  save(access, refresh) {
    sessionStorage.setItem("sso_access_token", access);
    sessionStorage.setItem("sso_refresh_token", refresh);
  },
  getAccess()  { return sessionStorage.getItem("sso_access_token"); },
  getRefresh() { return sessionStorage.getItem("sso_refresh_token"); },
  clear() {
    sessionStorage.removeItem("sso_access_token");
    sessionStorage.removeItem("sso_refresh_token");
  },
  isLoggedIn() { return !!sessionStorage.getItem("sso_access_token"); }
};

// ─────────────────────────────────────────────
// API HELPERS
// ─────────────────────────────────────────────

async function apiCall(endpoint, options = {}) {
  const token = TokenStore.getAccess();
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { "Authorization": `Bearer ${token}` } : {}),
    ...(options.headers || {})
  };

  const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });

  // If 401 and we have a refresh token, try to refresh
  if (res.status === 401 && TokenStore.getRefresh()) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      // Retry original request with new token
      const retryHeaders = { ...headers, "Authorization": `Bearer ${TokenStore.getAccess()}` };
      const retry = await fetch(`${API_BASE}${endpoint}`, { ...options, headers: retryHeaders });
      return retry;
    } else {
      redirectToLogin();
    }
  }
  return res;
}

async function tryRefreshToken() {
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: TokenStore.getRefresh() })
    });
    if (res.ok) {
      const data = await res.json();
      TokenStore.save(data.access_token, data.refresh_token);
      return true;
    }
  } catch {}
  return false;
}

function redirectToLogin() {
  TokenStore.clear();
  window.location.href = "/login";
}

// ─────────────────────────────────────────────
// JWT DECODE (client-side, no verification)
// ─────────────────────────────────────────────

function decodeJWT(token) {
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(base64));
  } catch {
    return null;
  }
}

// ─────────────────────────────────────────────
// UI HELPERS
// ─────────────────────────────────────────────

function showAlert(id, msg, type = "error") {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg;
  el.className = `alert show ${type}`;
  if (type === "error") {
    setTimeout(() => el.classList.remove("show"), 5000);
  }
}

function hideAlert(id) {
  const el = document.getElementById(id);
  if (el) el.className = "alert";
}

function setLoading(btnId, spinnerId, textId, loading, text) {
  const btn = document.getElementById(btnId);
  const sp  = document.getElementById(spinnerId);
  const tx  = document.getElementById(textId);
  if (btn) btn.disabled = loading;
  if (sp)  sp.style.display = loading ? "block" : "none";
  if (tx && text) tx.textContent = text;
}

function togglePassword(inputId) {
  const input = document.getElementById(inputId);
  input.type = input.type === "password" ? "text" : "password";
}

// ─────────────────────────────────────────────
// LOGIN PAGE FUNCTIONS
// ─────────────────────────────────────────────

function switchTab(tab) {
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  event.target.classList.add("active");

  document.getElementById("login-form").style.display    = tab === "login"    ? "block" : "none";
  document.getElementById("register-form").style.display = tab === "register" ? "block" : "none";
  hideAlert("alert");
}

async function handleLogin(e) {
  e.preventDefault();
  hideAlert("alert");

  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value;

  if (!username || !password) {
    showAlert("alert", "Please enter your username and password.");
    return;
  }

  setLoading("login-btn", "login-spinner", "login-btn-text", true, "Signing in...");

  try {
    // OAuth2 Password Flow requires form-encoded body
    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);

    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: formData
    });

    const data = await res.json();

    if (res.ok) {
      TokenStore.save(data.access_token, data.refresh_token);
      showAlert("alert", "✅ Login successful! Redirecting...", "success");
      setTimeout(() => { window.location.href = "/dashboard"; }, 800);
    } else {
      showAlert("alert", data.detail || "Login failed. Please try again.");
    }
  } catch (err) {
    showAlert("alert", "Network error. Is the server running?");
  } finally {
    setLoading("login-btn", "login-spinner", "login-btn-text", false, "Sign In");
  }
}

async function handleRegister(e) {
  e.preventDefault();
  hideAlert("alert");

  const username  = document.getElementById("reg-username").value.trim();
  const email     = document.getElementById("reg-email").value.trim();
  const password  = document.getElementById("reg-password").value;
  const full_name = document.getElementById("reg-fullname").value.trim();

  if (password.length < 8) {
    showAlert("alert", "Password must be at least 8 characters.");
    return;
  }

  setLoading("reg-btn", "reg-spinner", "reg-btn-text", true, "Creating account...");

  try {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, email, password, full_name })
    });

    const data = await res.json();

    if (res.ok) {
      showAlert("alert", "✅ Account created! Please sign in.", "success");
      document.getElementById("register-form").reset();
      // Switch to login tab
      setTimeout(() => {
        document.querySelectorAll(".tab-btn")[0].click();
        document.getElementById("login-username").value = username;
      }, 1200);
    } else {
      showAlert("alert", data.detail || "Registration failed. Please try again.");
    }
  } catch {
    showAlert("alert", "Network error. Is the server running?");
  } finally {
    setLoading("reg-btn", "reg-spinner", "reg-btn-text", false, "Create Account");
  }
}

// ─────────────────────────────────────────────
// DASHBOARD FUNCTIONS
// ─────────────────────────────────────────────

let currentUser = null;

async function initDashboard() {
  // Redirect if not logged in
  if (!TokenStore.isLoggedIn()) {
    window.location.href = "/login";
    return;
  }

  // Start clock
  updateClock();
  setInterval(updateClock, 1000);

  // Load current user
  await loadCurrentUser();
}

function updateClock() {
  const el = document.getElementById("clock");
  if (el) el.textContent = new Date().toLocaleString();
}

async function loadCurrentUser() {
  try {
    const res = await apiCall("/auth/me");
    if (!res.ok) { redirectToLogin(); return; }
    currentUser = await res.json();

    // Helper function to safely update element
    const safeUpdate = (id, value, prop = 'textContent') => {
      const el = document.getElementById(id);
      if (el) el[prop] = value;
    };

    // Update sidebar (exists on all dashboard pages)
    safeUpdate("sb-name", currentUser.full_name || currentUser.username);
    safeUpdate("sb-avatar", (currentUser.username[0] || "?").toUpperCase());

    const roleBadge = document.getElementById("sb-role");
    if (roleBadge) {
      roleBadge.textContent = currentUser.role;
      roleBadge.className = `badge role-badge ${currentUser.role}`;
    }

    // Show admin nav items
    if (currentUser.role === "admin") {
      const adminSection = document.getElementById("admin-section");
      if (adminSection) adminSection.style.display = "block";
      document.querySelectorAll(".admin-only").forEach(el => {
        el.style.display = el.tagName === 'A' ? 'flex' : 'block';
      });
    }

    // Populate overview (only exists on overview page)
    safeUpdate("ov-username", currentUser.username);
    safeUpdate("ov-email", currentUser.email);
    const ovRole = document.getElementById("ov-role");
    if (ovRole) {
      ovRole.innerHTML = `<span class="badge badge-${currentUser.role === 'admin' ? 'admin' : 'user'}">${currentUser.role}</span>`;
    }
    const ovStatus = document.getElementById("ov-status");
    if (ovStatus) {
      ovStatus.innerHTML = `<span class="badge badge-success">Active</span>`;
    }
    const ovSince = document.getElementById("ov-since");
    if (ovSince && currentUser.created_at) {
      ovSince.textContent = new Date(currentUser.created_at).toLocaleDateString();
    }
    safeUpdate("stat-role", currentUser.role.toUpperCase());

    // Populate profile (only exists on profile page)
    safeUpdate("profile-name", currentUser.full_name || currentUser.username);
    safeUpdate("profile-email", currentUser.email);
    safeUpdate("profile-avatar", (currentUser.username[0] || "?").toUpperCase());
    safeUpdate("upd-fullname", currentUser.full_name || "", "value");
    safeUpdate("upd-email", currentUser.email, "value");
    const prb = document.getElementById("profile-role-badge");
    if (prb) {
      prb.textContent = currentUser.role;
      prb.className = `badge badge-${currentUser.role === 'admin' ? 'admin' : 'user'}`;
    }

    // Populate token info (only exists on token page)
    const token = TokenStore.getAccess();
    const tokenDisplay = document.getElementById("token-display");
    if (tokenDisplay && token) {
      tokenDisplay.textContent = token;
      const payload = decodeJWT(token);
      if (payload) {
        safeUpdate("tok-userid", payload.sub);
        safeUpdate("tok-username", payload.username);
        safeUpdate("tok-role", payload.role);
        safeUpdate("tok-iat", payload.iat ? new Date(payload.iat * 1000).toLocaleString() : "—");
        safeUpdate("tok-exp", payload.exp ? new Date(payload.exp * 1000).toLocaleString() : "—");
      }
    }

    // Load stats if admin
    if (currentUser.role === "admin") {
      loadStats();
    }

  } catch (err) {
    console.error("Error loading user:", err);
    redirectToLogin();
  }
}

async function loadStats() {
  try {
    const [usersRes, appsRes] = await Promise.all([
      apiCall("/users/"),
      apiCall("/apps/")
    ]);
    
    // Safely update stats (only exist on overview page)
    if (usersRes.ok) {
      const data = await usersRes.json();
      const statUsers = document.getElementById("stat-users");
      if (statUsers) statUsers.textContent = data.total || 0;
    }
    if (appsRes.ok) {
      const apps = await appsRes.json();
      const statApps = document.getElementById("stat-apps");
      if (statApps) statApps.textContent = apps.length || 0;
    }
  } catch (err) {
    console.error("Error loading stats:", err);
  }
}

function showPage(page) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));

  const pageEl = document.getElementById(`page-${page}`);
  if (pageEl) pageEl.classList.add("active");

  const titles = {
    overview: "Overview", profile: "My Profile", token: "Token Info",
    users: "User Management", apps: "Applications", logs: "Audit Logs"
  };
  document.getElementById("page-title").textContent = titles[page] || page;

  // Lazy-load admin pages
  if (page === "users") loadUsers();
  if (page === "apps")  loadApps();
  if (page === "logs")  loadLogs();
}

// ── USERS TABLE ──

async function loadUsers() {
  document.getElementById("users-loading").style.display = "block";
  document.getElementById("users-table").style.display   = "none";

  try {
    const res = await apiCall("/users/");
    if (!res.ok) throw new Error();
    const data = await res.json();

    const tbody = document.getElementById("users-tbody");
    tbody.innerHTML = data.users.map(u => `
      <tr>
        <td>${u.id}</td>
        <td><strong>${u.username}</strong></td>
        <td>${u.email}</td>
        <td><span class="badge badge-${u.role === 'admin' ? 'admin' : 'user'}">${u.role}</span></td>
        <td><span class="badge badge-${u.is_active ? 'success' : 'danger'}">${u.is_active ? 'Active' : 'Disabled'}</span></td>
        <td>${new Date(u.created_at).toLocaleDateString()}</td>
        <td>
          <button class="btn-sm btn-danger" onclick="deleteUser(${u.id}, '${u.username}')">🗑 Delete</button>
        </td>
      </tr>
    `).join("") || `<tr><td colspan="7" class="empty-state">No users found</td></tr>`;

    document.getElementById("users-loading").style.display = "none";
    document.getElementById("users-table").style.display   = "block";
  } catch {
    document.getElementById("users-loading").textContent = "Failed to load users.";
  }
}

async function deleteUser(id, username) {
  if (!confirm(`Delete user "${username}"? This cannot be undone.`)) return;
  try {
    const res = await apiCall(`/users/${id}`, { method: "DELETE" });
    if (res.ok) loadUsers();
    else alert("Failed to delete user.");
  } catch { alert("Network error."); }
}

// ── APPS TABLE ──

async function loadApps() {
  document.getElementById("apps-loading").style.display = "block";
  document.getElementById("apps-table").style.display   = "none";

  try {
    const res = await apiCall("/apps/");
    if (!res.ok) throw new Error();
    const apps = await res.json();

    const tbody = document.getElementById("apps-tbody");
    tbody.innerHTML = apps.map(a => `
      <tr>
        <td>${a.id}</td>
        <td><strong>${a.name}</strong></td>
        <td><code style="font-size:0.75rem">${a.client_id}</code></td>
        <td><a href="${a.redirect_uri}" target="_blank" style="color:var(--primary)">${a.redirect_uri.substring(0,30)}...</a></td>
        <td><span class="badge badge-${a.is_active ? 'success' : 'danger'}">${a.is_active ? 'Active' : 'Inactive'}</span></td>
        <td>
          <button class="btn-sm btn-danger" onclick="deleteApp(${a.id}, '${a.name}')">🗑 Remove</button>
        </td>
      </tr>
    `).join("") || `<tr><td colspan="6" class="empty-state">No applications registered</td></tr>`;

    document.getElementById("apps-loading").style.display = "none";
    document.getElementById("apps-table").style.display   = "block";
  } catch {
    document.getElementById("apps-loading").textContent = "Failed to load applications.";
  }
}

async function registerApp(e) {
  e.preventDefault();
  const name        = document.getElementById("app-name").value.trim();
  const redirect_uri = document.getElementById("app-redirect").value.trim();
  const description = document.getElementById("app-desc").value.trim();

  try {
    const res = await apiCall("/apps/register", {
      method: "POST",
      body: JSON.stringify({ name, redirect_uri, description })
    });
    const data = await res.json();
    if (res.ok) {
      // Show credentials to user (only shown once!)
      alert(`✅ Application Registered!\n\nClient ID: ${data.client_id}\nClient Secret: ${data.client_secret}\n\n⚠️ Save your client_secret now — it won't be shown again!`);
      e.target.reset();
      loadApps();
      loadStats();
    } else {
      const alertBox = document.getElementById("app-alert");
      alertBox.textContent = data.detail || "Registration failed.";
      alertBox.className = "alert-box show error";
    }
  } catch {
    alert("Network error.");
  }
}

async function deleteApp(id, name) {
  if (!confirm(`Remove application "${name}"?`)) return;
  try {
    const res = await apiCall(`/apps/${id}`, { method: "DELETE" });
    if (res.ok) { loadApps(); loadStats(); }
    else alert("Failed to remove application.");
  } catch { alert("Network error."); }
}

// ── AUDIT LOGS ──

async function loadLogs() {
  document.getElementById("logs-loading").style.display = "block";
  document.getElementById("logs-table").style.display   = "none";

  try {
    const res = await apiCall("/users/logs");
    if (!res.ok) throw new Error();
    const logs = await res.json();

    const tbody = document.getElementById("logs-tbody");
    tbody.innerHTML = logs.map(l => `
      <tr>
        <td>${l.id}</td>
        <td>${l.username_attempted || (l.user_id ? `#${l.user_id}` : "—")}</td>
        <td>${new Date(l.login_time).toLocaleString()}</td>
        <td><code>${l.ip_address || "—"}</code></td>
        <td><span class="badge badge-${l.success ? 'success' : 'danger'}">${l.success ? '✅ Success' : '❌ Failed'}</span></td>
        <td>${l.failure_reason || "—"}</td>
      </tr>
    `).join("") || `<tr><td colspan="6" class="empty-state">No logs found</td></tr>`;

    document.getElementById("logs-loading").style.display = "none";
    document.getElementById("logs-table").style.display   = "block";
  } catch {
    document.getElementById("logs-loading").textContent = "Failed to load logs.";
  }
}

// ── PROFILE UPDATE ──

async function updateProfile(e) {
  e.preventDefault();
  const fullname = document.getElementById("upd-fullname").value.trim();
  const email    = document.getElementById("upd-email").value.trim();
  const password = document.getElementById("upd-password").value;

  const payload = { full_name: fullname, email };
  if (password) payload.password = password;

  try {
    const res = await apiCall(`/users/${currentUser.id}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      const alertBox = document.getElementById("profile-alert");
      alertBox.textContent = "✅ Profile updated successfully!";
      alertBox.className = "alert-box show success";
      currentUser = data;
      document.getElementById("profile-name").textContent = data.full_name || data.username;
      document.getElementById("sb-name").textContent = data.full_name || data.username;
      setTimeout(() => alertBox.classList.remove("show"), 3000);
    } else {
      const alertBox = document.getElementById("profile-alert");
      alertBox.textContent = data.detail || "Update failed.";
      alertBox.className = "alert-box show error";
    }
  } catch {
    alert("Network error.");
  }
}

// ── LOGOUT ──

async function logout() {
  try {
    await apiCall("/auth/logout", { method: "POST" });
  } catch {}
  TokenStore.clear();
  window.location.href = "/login";
}

// ─────────────────────────────────────────────
// AUTO-REDIRECT: If already logged in, skip login page
// ─────────────────────────────────────────────
if (window.location.pathname.includes("/login") && TokenStore.isLoggedIn()) {
  window.location.href = "/dashboard";
}
