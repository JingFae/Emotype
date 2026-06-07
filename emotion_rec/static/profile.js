(function () {
  "use strict";

  // Require login
  if (typeof Auth === "undefined" || !Auth.isLoggedIn()) {
    window.location.href = "/login";
    return;
  }

  var els = {
    avatar: document.getElementById("profileAvatar"),
    displayName: document.getElementById("profileDisplayName"),
    meta: document.getElementById("profileMeta"),
    role: document.getElementById("profileRole"),
    form: document.getElementById("profileSettingsForm"),
    settingsDisplayName: document.getElementById("settingsDisplayName"),
    settingsCurrentPassword: document.getElementById("settingsCurrentPassword"),
    settingsNewPassword: document.getElementById("settingsNewPassword"),
    settingsLang: document.getElementById("settingsLang"),
    settingsLocalMode: document.getElementById("settingsLocalMode"),
    settingsStatus: document.getElementById("settingsStatus"),
    adminSection: document.getElementById("adminSection"),
    adminUsersBody: document.getElementById("adminUsersBody"),
    adminRecordView: document.getElementById("adminRecordView"),
    adminRecordTitle: document.getElementById("adminRecordTitle"),
    adminRecordList: document.getElementById("adminRecordList"),
    adminRecordClose: document.getElementById("adminRecordClose"),
  };

  var currentUser = Auth.getUser();

  function setSettingsStatus(msg, type) {
    els.settingsStatus.textContent = msg || "";
    els.settingsStatus.className = "profile-status" + (type ? " " + type : "");
  }

  function formatDate(isoStr) {
    if (!isoStr) return "--";
    try {
      var d = new Date(isoStr);
      return d.getFullYear() + "-" +
        String(d.getMonth() + 1).padStart(2, "0") + "-" +
        String(d.getDate()).padStart(2, "0");
    } catch (e) {
      return isoStr;
    }
  }

  // Populate user info
  function renderUserInfo(user) {
    var name = user.display_name || user.username;
    var initial = (name || "?")[0].toUpperCase();
    els.avatar.textContent = initial;
    els.displayName.textContent = name;
    els.meta.textContent = "@" + user.username + " · 注册于 " + formatDate(user.created_at);
    els.role.textContent = user.role === "admin" ? "管理员" : "用户";
    els.settingsDisplayName.value = user.display_name || "";
  }

  renderUserInfo(currentUser);

  // --- Language & Local Mode settings ---
  var savedLang = localStorage.getItem("emomirror.lang") || "zh";
  if (els.settingsLang) els.settingsLang.value = savedLang;

  if (els.settingsLang) {
    els.settingsLang.addEventListener("change", function () {
      localStorage.setItem("emomirror.lang", els.settingsLang.value);
      // Reload page so language change takes effect immediately
      window.location.reload();
    });
  }

  var savedLocalMode = localStorage.getItem("emomirror.localMode") !== "false";
  if (els.settingsLocalMode) els.settingsLocalMode.checked = savedLocalMode;

  if (els.settingsLocalMode) {
    els.settingsLocalMode.addEventListener("change", function () {
      localStorage.setItem("emomirror.localMode", els.settingsLocalMode.checked ? "true" : "false");
    });
  }

  // Load fresh user data
  Auth.apiJson("/api/auth/me")
    .then(function (data) {
      currentUser = data;
      renderUserInfo(data);
    })
    .catch(function (err) {
      // Token might be expired, handled by Auth.apiJson
    });

  // Settings form
  els.form.addEventListener("submit", function (e) {
    e.preventDefault();
    setSettingsStatus("保存中...", "");

    var promises = [];
    var newName = els.settingsDisplayName.value.trim();
    var currentPw = els.settingsCurrentPassword.value;
    var newPw = els.settingsNewPassword.value;

    // Update display name if changed
    if (newName && newName !== (currentUser.display_name || currentUser.username)) {
      promises.push(
        Auth.apiJson("/api/auth/me", {
          method: "PUT",
          body: JSON.stringify({ display_name: newName }),
        })
      );
    }

    // Update password if both fields filled
    if (currentPw && newPw) {
      promises.push(
        Auth.apiJson("/api/auth/me/password", {
          method: "PUT",
          body: JSON.stringify({
            current_password: currentPw,
            new_password: newPw,
          }),
        })
      );
    }

    if (promises.length === 0) {
      setSettingsStatus("没有需要保存的修改。", "");
      return;
    }

    Promise.all(promises)
      .then(function (results) {
        // Refresh user data
        return Auth.apiJson("/api/auth/me");
      })
      .then(function (data) {
        currentUser = data;
        renderUserInfo(data);
        // Update stored user
        var auth = JSON.parse(localStorage.getItem("emomirror.auth") || "{}");
        auth.user = data;
        localStorage.setItem("emomirror.auth", JSON.stringify(auth));

        els.settingsCurrentPassword.value = "";
        els.settingsNewPassword.value = "";
        setSettingsStatus("保存成功！", "success");
        setTimeout(function () {
          setSettingsStatus("");
        }, 3000);
      })
      .catch(function (err) {
        setSettingsStatus(err.message || "保存失败", "error");
      });
  });

  // --- Admin section ---
  if (Auth.isAdmin()) {
    els.adminSection.style.display = "";

    // Load user list
    Auth.apiJson("/api/admin/users")
      .then(function (data) {
        var users = data.users || [];
        els.adminUsersBody.innerHTML = "";
        users.forEach(function (u) {
          var tr = document.createElement("tr");
          tr.innerHTML =
            "<td>" + u.username + "</td>" +
            "<td>" + (u.display_name || "-") + "</td>" +
            '<td><span class="status-pill">' +
              (u.role === "admin" ? "管理员" : "用户") +
            "</span></td>" +
            "<td>" + formatDate(u.created_at) + "</td>" +
            "<td>" + formatDate(u.last_login_at) + "</td>" +
            '<td class="admin-action-cell">' +
              '<button class="warm-btn ghost admin-view-btn" data-username="' + u.username + '">查看记录</button> ' +
              '<button class="warm-btn ghost admin-export-json-btn" data-username="' + u.username + '">导出JSON</button> ' +
              '<button class="warm-btn ghost admin-export-csv-btn" data-username="' + u.username + '">导出CSV</button>' +
            "</td>";
          els.adminUsersBody.appendChild(tr);
        });
        if (users.length === 0) {
          els.adminUsersBody.innerHTML = '<tr><td colspan="6">暂无用户</td></tr>';
        }
      })
      .catch(function (err) {
        els.adminUsersBody.innerHTML =
          '<tr><td colspan="6">加载失败: ' + err.message + "</td></tr>";
      });

    // Delegate clicks for admin action buttons
    els.adminUsersBody.addEventListener("click", function (e) {
      var btn = e.target.closest("button");
      if (!btn) return;

      var username = btn.getAttribute("data-username");
      if (!username) return;

      if (btn.classList.contains("admin-view-btn")) {
        loadAdminRecords(username);
      } else if (btn.classList.contains("admin-export-json-btn")) {
        window.open("/participants/" + encodeURIComponent(username) + "/export.json", "_blank");
      } else if (btn.classList.contains("admin-export-csv-btn")) {
        window.open("/participants/" + encodeURIComponent(username) + "/export.csv", "_blank");
      }
    });

    // Admin record viewer
    function loadAdminRecords(username) {
      if (!els.adminRecordView) return;
      els.adminRecordTitle.textContent = username + " 的记录";
      els.adminRecordList.innerHTML = '<tr><td colspan="3">加载中...</td></tr>';
      els.adminRecordView.style.display = "";

      Auth.apiJson("/api/admin/records?participant_code=" + encodeURIComponent(username))
        .then(function (data) {
          var records = data.records || [];
          els.adminRecordList.innerHTML = "";
          if (records.length === 0) {
            els.adminRecordList.innerHTML = '<tr><td colspan="3">暂无记录</td></tr>';
            return;
          }
          records.forEach(function (r) {
            var tr = document.createElement("tr");
            tr.innerHTML =
              "<td>" + (r.source_label || r.source || "-") + "</td>" +
              "<td>" + formatDate(r.created_at) + "</td>" +
              "<td>" + (r.text || r.content || "").substring(0, 80) + "</td>";
            els.adminRecordList.appendChild(tr);
          });
        })
        .catch(function (err) {
          els.adminRecordList.innerHTML =
            '<tr><td colspan="3">加载失败: ' + err.message + "</td></tr>";
        });
    }

    // Close admin record viewer
    if (els.adminRecordClose) {
      els.adminRecordClose.addEventListener("click", function () {
        if (els.adminRecordView) els.adminRecordView.style.display = "none";
      });
    }
  }
})();
