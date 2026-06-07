/**
 * EmoBridge Shared Auth Module
 *
 * Manages JWT tokens and user state in localStorage.
 * Every page loads this module to toggle login/profile UI.
 * - Logged in: shows profile tab, user badge, hides login tab
 * - Not logged in: shows login tab, hides profile tab
 * - On protected pages (/profile): auto-redirects to /login
 */
(function (global) {
  "use strict";

  var STORAGE_KEY = "emomirror.auth";
  var PARTICIPANT_KEY = "emomirror.participant";
  var NICKNAME_KEY = "emomirror.nickname";

  // Pages that REQUIRE auth (everything else is public)
  var PROTECTED_PAGES = ["/profile", "/admin"];

  // --- Token & User management ---

  function _load() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function _save(data) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (e) {}
  }

  function getToken() {
    var auth = _load();
    return auth ? auth.access_token : null;
  }

  function getUser() {
    var auth = _load();
    return auth ? auth.user : null;
  }

  function isLoggedIn() {
    return !!getToken();
  }

  function isAdmin() {
    var user = getUser();
    return user && user.role === "admin";
  }

  function saveAuth(data) {
    _save(data);
    if (data && data.user && data.user.username) {
      try {
        localStorage.setItem(
          PARTICIPANT_KEY,
          JSON.stringify({
            participant_code: data.user.username,
            consent_version: "user-v1",
          })
        );
      } catch (e) {}
    }
  }

  function logout() {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {}
    window.location.href = "/login";
  }

  // --- Authenticated fetch ---

  function apiJson(url, options) {
    options = options || {};
    var headers = Object.assign(
      { "Content-Type": "application/json; charset=utf-8" },
      options.headers || {}
    );
    var token = getToken();
    if (token) {
      headers["Authorization"] = "Bearer " + token;
    }
    return fetch(url, Object.assign({}, options, { headers: headers })).then(
      function (response) {
        if (response.status === 401) {
          logout();
          throw new Error("登录已过期，请重新登录。");
        }
        if (!response.ok) {
          return response.json().then(function (data) {
            throw new Error(
              data.detail || data.message || "请求失败 (" + response.status + ")"
            );
          });
        }
        return response.json();
      }
    );
  }

  // --- UI helpers ---

  function _currentPath() {
    return window.location.pathname;
  }

  function _isPublicPage() {
    var path = _currentPath();
    for (var i = 0; i < PROTECTED_PAGES.length; i++) {
      if (path === PROTECTED_PAGES[i] || path.startsWith(PROTECTED_PAGES[i] + "/")) return false;
    }
    return true;
  }

  function updateNavbar() {
    var profileTab = document.getElementById("profileTab");
    var authTab = document.getElementById("authTab");
    var topbarRight = document.querySelector(".topbar-right");

    if (isLoggedIn()) {
      // --- Logged in state ---
      var user = getUser();
      if (profileTab) profileTab.style.display = "";
      if (authTab) authTab.style.display = "none";

      // Add user badge + logout button to topbar
      if (topbarRight && !document.getElementById("authUserBadge")) {
        var badge = document.createElement("a");
        badge.className = "auth-user-badge";
        badge.id = "authUserBadge";
        badge.href = "/profile";
        badge.title = "个人信息";

        var avatarSpan = document.createElement("span");
        avatarSpan.className = "auth-avatar-mini";
        avatarSpan.textContent = (user.display_name || user.username || "?")[0].toUpperCase();

        var nameSpan = document.createElement("span");
        nameSpan.className = "auth-user-name";
        nameSpan.textContent = user.display_name || user.username;

        badge.appendChild(avatarSpan);
        badge.appendChild(nameSpan);
        topbarRight.insertBefore(badge, topbarRight.firstChild);

        var logoutBtn = document.createElement("button");
        logoutBtn.className = "auth-logout-btn";
        logoutBtn.id = "authLogoutBtn";
        logoutBtn.textContent = "退出";
        logoutBtn.addEventListener("click", function (e) {
          e.preventDefault();
          logout();
        });
        topbarRight.insertBefore(logoutBtn, badge.nextSibling);
      }
    } else {
      // --- Not logged in state ---
      if (profileTab) profileTab.style.display = "none";
      if (authTab) authTab.style.display = "none";  // hide from nav; login link goes in topbar-right

      var logoutBtn = document.getElementById("authLogoutBtn");
      if (logoutBtn) logoutBtn.remove();

      // Show guest nickname badge + login link in topbar-right
      if (topbarRight && !document.getElementById("authUserBadge")) {
        var nickname;
        try { nickname = localStorage.getItem(NICKNAME_KEY) || ""; } catch (e) { nickname = ""; }
        var badge = document.createElement("button");
        badge.className = "auth-user-badge auth-guest-badge";
        badge.id = "authUserBadge";
        badge.type = "button";
        badge.title = "点击设置昵称";

        var avatarSpan = document.createElement("span");
        avatarSpan.className = "auth-avatar-mini auth-avatar-guest";
        avatarSpan.textContent = nickname ? nickname[0].toUpperCase() : "访";

        var nameSpan = document.createElement("span");
        nameSpan.className = "auth-user-name";
        nameSpan.id = "authGuestName";
        nameSpan.textContent = nickname || "访客";

        badge.appendChild(avatarSpan);
        badge.appendChild(nameSpan);
        badge.addEventListener("click", function () {
          var current;
          try { current = localStorage.getItem(NICKNAME_KEY) || ""; } catch (e) { current = ""; }
          var newName = prompt("设置你的昵称（留空恢复默认）：", current);
          if (newName === null) return;
          newName = newName.trim().slice(0, 20);
          try { localStorage.setItem(NICKNAME_KEY, newName); } catch (e) {}
          var display = newName || "访客";
          document.getElementById("authGuestName").textContent = display;
          document.querySelector("#authUserBadge .auth-avatar-guest").textContent = display[0].toUpperCase();
        });
        topbarRight.insertBefore(badge, topbarRight.firstChild);

        // Login link placed right after the guest badge
        if (!document.getElementById("authLoginLink")) {
          var loginLink = document.createElement("a");
          loginLink.className = "auth-login-link";
          loginLink.id = "authLoginLink";
          loginLink.href = "/login";
          loginLink.textContent = "登录";
          topbarRight.insertBefore(loginLink, badge.nextSibling);
        }
      }

      // Auto-redirect to login page if on a protected page
      if (!_isPublicPage()) {
        window.location.href = "/login";
      }
    }
  }

  // Auto-init on every page
  function initNavbar() {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", updateNavbar);
    } else {
      updateNavbar();
    }
  }

  // Expose as global Auth object
  global.Auth = {
    getToken: getToken,
    getUser: getUser,
    isLoggedIn: isLoggedIn,
    isAdmin: isAdmin,
    saveAuth: saveAuth,
    logout: logout,
    apiJson: apiJson,
    updateNavbar: updateNavbar,
    initNavbar: initNavbar,
  };

  // Auto-init immediately (auth.js is loaded without defer)
  initNavbar();
})(window);
