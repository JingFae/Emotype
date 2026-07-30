# Emotype_lzy_db 改动文档

> 基于 `Emotype_v0(rich)` (commit `71e501a`) 的改动清单
> 作者：lzy（数据库搭建与连接方向）
> 日期：2026-06-06

---

## 一、项目定位

`Emotype_lzy_db` 是从 `Emotype_v0(rich)` fork 的数据库方向分支，主要新增了**用户认证系统（JWT）**、**数据库用户管理**、**前端国际化（i18n）**以及一系列**UI 优化**。

---

## 二、后端改动

### 2.1 用户认证系统 (`emotion_rec/app.py`, +263 行)

| 新增功能 | 说明 |
|----------|------|
| JWT Token 系统 | `_create_access_token()` / `_verify_token()`，HS256 签名，自动生成 SECRET_KEY |
| 注册接口 | `POST /api/auth/register` — 用户名 + 密码注册，首个用户自动成为管理员 |
| 登录接口 | `POST /api/auth/login` — 返回 JWT access_token |
| 用户信息 | `GET /api/auth/me` — 获取当前登录用户 |
| 修改资料 | `PUT /api/auth/me` — 修改显示名 |
| 修改密码 | `PUT /api/auth/me/password` — 旧密码验证 + 新密码设置 |
| 用户设置 | `GET/PUT /api/auth/me/settings` — 语言、主题等偏好 |
| 管理员接口 | `GET /api/admin/users` — 管理员查看所有用户列表 |
| 管理员记录 | `GET /api/admin/records` — 支持 JWT session 管理员认证（原有仅支持 ADMIN_TOKEN） |
| 登录页面路由 | `GET /login` / `GET /profile` — 服务前端页面 |

新增 Pydantic 模型：`RegisterRequest`, `LoginRequest`, `PasswordChangeRequest`, `ProfileUpdateRequest`, `SettingsUpdateRequest`

### 2.2 数据库扩展 (`emotion_rec/storage.py`, +303 行)

| 新增表 | 字段 |
|--------|------|
| `users` | id, username, hashed_password, display_name, role (admin/user), participant_id (FK), is_active, created_at, last_login_at |
| `user_settings` | id, user_id (FK), language, theme, preferences_json |

关键函数：
- `create_user()` — 创建用户，自动关联 participant
- `authenticate_user()` — bcrypt 密码验证（带 SHA-256 fallback）
- `_ensure_sqlite_user_schema()` — 自动迁移，为旧数据库添加新列
- `get_or_create_user_settings()` — 获取或创建用户设置
- `list_all_users()` — 管理员列表

### 2.3 新增依赖 (`requirements.txt`)

```
passlib[bcrypt]>=1.7.4
bcrypt>=4.0.0,<5.0.0
PyJWT>=2.8.0
```

---

## 三、前端改动

### 3.1 新增页面（7 个文件）

| 文件 | 说明 |
|------|------|
| `login.html` / `login.js` / `login.css` | 登录/注册页面 |
| `profile.html` / `profile.js` / `profile.css` | 个人中心（用户信息、账户设置、语言偏好、本地模式、管理员用户管理） |
| `auth.js` | 共享认证模块 — JWT 管理、导航栏动态更新、自动重定向 |
| `i18n.js` | 共享国际化模块 — 所有页面的中英文切换 |

### 3.2 profile.html 个人中心功能

- **用户信息卡片**：头像（首字母）、显示名、用户名、角色、注册日期
- **账户设置**：修改显示名、修改密码（带「保存修改」按钮）
- **偏好设置**：语言偏好（中文/English，即时切换）、本地模式（checkbox 占位）
- **快捷入口**：历史记录、情绪复盘、日记本、身体感受
- **管理员区域**（仅管理员可见）：
  - 用户列表表格（用户名、显示名、角色、注册时间、最后登录、操作）
  - 每个用户有「查看记录」「导出 JSON」「导出 CSV」操作按钮
  - 记录查看器（来源、日期、内容摘要）

### 3.3 首页 UI 优化 (`index.html`, `app.js`)

| 改动 | 说明 |
|------|------|
| 移除研究模式面板 | 从首页删除 `<details class="participant-panel">`，功能移至管理员个人中心 |
| 移除 EN 语言切换 | 从 topbar-right 移至个人中心设置 |
| 移除本地模式 checkbox | 从 topbar-right 移至个人中心设置 |
| topbar-right 清空 | 不再显示多余标签，仅由 auth.js 动态添加用户头像 badge |
| Brand-mark 统一 | 首页从 `<div>` 改为 `<a href="/">` 可点击，与其他页面一致 |
| 数据视图导出按钮 | 重命名 ID 避免重复 (`dataExportJson` / `dataExportCsv`) |
| i18n 初始化 | `initI18n()` 简化，不再绑定页面内按钮（语言由个人中心控制） |

### 3.4 子页面统一改动 (`diary.html`, `review.html`, `records.html`, `body_sensation.html`)

| 改动 | 说明 |
|------|------|
| 导航栏加 data-i18n | 所有 tab 按钮加 `data-i18n` 属性支持中英文切换 |
| 新增「个人信息」tab | 所有页面导航加个人信息入口 |
| 新增「数据」tab | 统一位置在「身体感受」与「个人信息」之间 |
| topbar-right 清空 | 删除原有的 session-label（"正式日记"、"阶段性复盘"、"个人记录"、"Body Sense"）和 status-pill |
| 加载 i18n.js + auth.js | 每个子页面加载共享模块 |
| Brand-mark 可点击 | 保持 `<a href="/">` 链接 |
| profileTab 缩进修复 | 修正复制粘贴导致的缩进不一致 |

### 3.5 body_sensation 页面特殊改动

- 删除「实验编号」输入框和 participant code 相关 UI
- `currentParticipantCode()` 优先使用 Auth 登录用户的 username
- `apiJson()` 优先使用 `Auth.apiJson`（带 JWT token）

### 3.6 子页面 JS 清理 (`diary.js`, `review.js`, `records.js`, `body_sensation.js`)

- 移除 `els.participant` / `els.participantBadge` 引用（对应 HTML 元素已删除）
- 移除 `els.participant.textContent = ...` 赋值
- 移除 `participantForm.addEventListener` / `exportParticipantJson.addEventListener` 等事件绑定

### 3.7 `auth.js` 认证模块

- `updateNavbar()`：登录时显示个人信息 tab，隐藏登录 tab；未登录时重定向到登录页
- 动态插入用户头像 badge（首字母 + 用户名，链接到 /profile）和退出按钮
- `Auth.apiJson()`：所有 API 调用自动携带 JWT Bearer token
- `Auth.saveAuth()`：登录时自动将 username 写入 participant_code

### 3.8 `i18n.js` 国际化模块

- 读取 `localStorage("emomirror.lang")` 应用翻译
- 覆盖所有页面的：导航栏、页面标题、标签、按钮、表单标签
- 支持 `data-i18n`（文本）和 `data-i18n-placeholder`（placeholder）

---

## 四、文件变更汇总

### 新增文件（7 个）

```
emotion_rec/static/auth.js          — JWT 认证模块
emotion_rec/static/i18n.js          — 国际化翻译模块
emotion_rec/static/login.html       — 登录页
emotion_rec/static/login.js         — 登录逻辑
emotion_rec/static/login.css        — 登录样式
emotion_rec/static/profile.html     — 个人中心页
emotion_rec/static/profile.js       — 个人中心逻辑
emotion_rec/static/profile.css      — 个人中心样式
```

### 修改文件（13 个）

```
emotion_rec/app.py                  — +263 行（JWT 认证、用户 API、管理员记录 API）
emotion_rec/storage.py              — +303 行（users 表、user_settings 表、CRUD）
emotion_rec/static/index.html       — 删除研究面板、清空 topbar、brand-mark 改为 a
emotion_rec/static/app.js           — 清理研究模式引用、简化 i18n
emotion_rec/static/styles.css       — +66 行（auth badge 样式）
emotion_rec/static/diary.html       — topbar 清理、加 data-i18n、加数据 tab
emotion_rec/static/diary.js         — 移除 participant 引用
emotion_rec/static/review.html      — topbar 清理、加 data-i18n、加数据 tab
emotion_rec/static/review.js        — 移除 participant 引用
emotion_rec/static/records.html     — topbar 清理、加 data-i18n、加数据 tab
emotion_rec/static/records.js       — 移除 participant 引用
emotion_rec/static/body_sensation.html — 删除实验编号输入、加 data-i18n
emotion_rec/static/body_sensation.js — 用 Auth 用户名替代 participant code
requirements.txt                    — +3 依赖
```

---

## 五、与主项目 Emotype 的关系

```
GitHub: JingFae/Emotype (Rich branch)
    │
    ├── commit 71e501a  "feat: add personal records and improve review insights"
    │       │
    │       ├── /root/Emotype_v0(rich)     [原始 fork，无改动]
    │       │
    │       └── /root/Emotype_lzy_db       [本文档描述的所有改动，未提交]
    │
    └── commit 8792ee4  "docs: update README"  ← /root/Emotype 主项目（仅文档更新）
```

- **主项目 `/root/Emotype`** 仅比 rich 多一个文档 commit，代码完全一致
- **合并策略**：将 lzy_db 的代码改动合并到主项目，同时保留主项目的最新文档
- **备份**：`/root/Emotype_backup_20260606`

---

## 六、数据库表结构变化

### 原有表（3 个）

| 表名 | 用途 |
|------|------|
| participants | 实验参与者编号 |
| diary_entries | 随手记日记 |
| usage_events | 使用事件日志 |

### 新增表（2 个）

| 表名 | 用途 |
|------|------|
| users | 用户账号（用户名、密码、角色、关联 participant） |
| user_settings | 用户偏好设置（语言、主题、JSON 扩展） |

### 额外新增（已在 rich 中存在）

| 表名 | 用途 |
|------|------|
| formal_diaries | 正式日记 |
| emotion_review_reports | 情绪复盘报告缓存 |
