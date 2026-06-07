(function () {
  "use strict";

  // If already logged in, redirect to profile
  if (typeof Auth !== "undefined" && Auth.isLoggedIn()) {
    window.location.href = "/profile";
    return;
  }

  var els = {
    loginTab: document.getElementById("loginTab"),
    registerTab: document.getElementById("registerTab"),
    loginForm: document.getElementById("loginForm"),
    registerForm: document.getElementById("registerForm"),
    loginUsername: document.getElementById("loginUsername"),
    loginPassword: document.getElementById("loginPassword"),
    regUsername: document.getElementById("regUsername"),
    regPassword: document.getElementById("regPassword"),
    regDisplayName: document.getElementById("regDisplayName"),
    status: document.getElementById("loginStatus"),
    welcomeText: document.getElementById("welcomeText"),
  };

  function setStatus(msg, type) {
    els.status.textContent = msg || "";
    els.status.className = "login-status" + (type ? " " + type : "");
  }

  function showLogin() {
    els.loginTab.classList.add("is-active");
    els.registerTab.classList.remove("is-active");
    els.loginForm.style.display = "";
    els.registerForm.style.display = "none";
    els.welcomeText.innerHTML = "<h1>欢迎回来</h1><p>登录你的 EmoBridge 账户，继续情绪之旅</p>";
    setStatus("");
  }

  function showRegister() {
    els.registerTab.classList.add("is-active");
    els.loginTab.classList.remove("is-active");
    els.registerForm.style.display = "";
    els.loginForm.style.display = "none";
    els.welcomeText.innerHTML = "<h1>创建新账户</h1><p>第一个注册的用户将自动成为管理员</p>";
    setStatus("");
  }

  els.loginTab.addEventListener("click", showLogin);
  els.registerTab.addEventListener("click", showRegister);

  // Login
  els.loginForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var username = els.loginUsername.value.trim();
    var password = els.loginPassword.value;
    if (!username || !password) {
      setStatus("请输入用户名和密码。", "error");
      return;
    }
    setStatus("正在登录...", "");
    fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: username, password: password }),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) throw new Error(data.detail || "登录失败");
          return data;
        });
      })
      .then(function (data) {
        Auth.saveAuth(data);
        setStatus("登录成功！正在跳转...", "success");
        setTimeout(function () {
          window.location.href = "/";
        }, 500);
      })
      .catch(function (err) {
        setStatus(err.message, "error");
      });
  });

  // Register
  els.registerForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var username = els.regUsername.value.trim();
    var password = els.regPassword.value;
    var displayName = els.regDisplayName.value.trim();
    if (!username || !password) {
      setStatus("请输入用户名和密码。", "error");
      return;
    }
    setStatus("正在注册...", "");
    fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: username,
        password: password,
        display_name: displayName || null,
      }),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) throw new Error(data.detail || "注册失败");
          return data;
        });
      })
      .then(function (data) {
        Auth.saveAuth(data);
        var roleMsg = data.user.role === "admin" ? "（你已成为管理员）" : "";
        setStatus("注册成功！" + roleMsg + " 正在跳转...", "success");
        setTimeout(function () {
          window.location.href = "/";
        }, 800);
      })
      .catch(function (err) {
        setStatus(err.message, "error");
      });
  });

  // Focus first input
  els.loginUsername.focus();
})();
