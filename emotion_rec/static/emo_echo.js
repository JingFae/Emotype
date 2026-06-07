/* ============================================
   Emo Echo — Chat Logic
   ============================================ */

(function () {
  'use strict';

  // --- State ---
  let sessionId = _newSessionId();
  let history = [];
  let isSending = false;

  // --- DOM refs ---
  const messagesEl    = document.getElementById('echoMessages');
  const inputEl       = document.getElementById('echoInput');
  const sendBtn       = document.getElementById('echoSendBtn');
  const typingEl      = document.getElementById('echoTyping');
  const clearBtn      = document.getElementById('echoClearBtn');
  const historyBtn    = document.getElementById('echoHistoryBtn');
  const historyPanel  = document.getElementById('echoHistoryPanel');
  const historyClose  = document.getElementById('echoHistoryClose');
  const sessionListEl = document.getElementById('echoSessionList');

  // --- Init ---
  function init() {
    _showWelcome();
    sendBtn.addEventListener('click', _handleSend);
    inputEl.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        _handleSend();
      }
    });
    inputEl.addEventListener('input', _autoResize);
    clearBtn.addEventListener('click', _clearChat);
    historyBtn.addEventListener('click', _openHistory);
    historyClose.addEventListener('click', function () {
      historyPanel.style.display = 'none';
    });
  }

  function _showWelcome() {
    messagesEl.innerHTML = '';
    history = [];
    _appendBotMsg('你好，我是 Emo 回响，心事诉说，情绪皆有回响。\n\n有什么想跟我说的吗？');
  }

  // --- Send message ---
  function _handleSend() {
    const text = inputEl.value.trim();
    if (!text || isSending) return;

    _appendUserMsg(text);
    history.push({ role: 'user', content: text });
    inputEl.value = '';
    _autoResize();
    _setLoading(true);

    _sendToApi(text)
      .then(function (reply) {
        _setLoading(false);
        _appendBotMsg(reply);
        history.push({ role: 'assistant', content: reply });
        if (history.length > 20) history = history.slice(-20);
      })
      .catch(function (err) {
        console.error('[emo_echo]', err);
        _setLoading(false);
        _appendBotMsg(_t('echo.fallback', '抱歉，我现在有点走神了，等一下再试试吧。'));
      });
  }

  function _getParticipantCode() {
    try {
      const raw = localStorage.getItem('emomirror.participant');
      if (raw) {
        const p = JSON.parse(raw);
        if (p && p.participant_code) return p.participant_code;
      }
    } catch (e) {}
    return localStorage.getItem('participant_code') || 'local';
  }

  async function _sendToApi(message) {
    const token = localStorage.getItem('auth_token') || '';
    const participantCode = _getParticipantCode();

    const payload = {
      message: message,
      session_id: sessionId,
      history: history.slice(-10),
      participant_code: participantCode,
    };

    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = 'Bearer ' + token;

    const res = await fetch('/api/emo-echo/chat', {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error('API error ' + res.status);
    }
    const data = await res.json();
    return data.reply || '嗯，我在这里。';
  }

  // --- DOM helpers ---
  function _appendBotMsg(text) {
    const row = document.createElement('div');
    row.className = 'echo-msg is-bot';
    row.innerHTML =
      '<img class="echo-avatar-sm" src="/static/icon_chatbox.png" alt="" aria-hidden="true" />' +
      '<div>' +
        '<div class="echo-bubble">' + _escapeHtml(text) + '</div>' +
        '<div class="echo-time">' + _timeStr() + '</div>' +
      '</div>';
    messagesEl.appendChild(row);
    _scrollToBottom();
  }

  function _appendUserMsg(text) {
    const initial = _getUserInitial();
    const row = document.createElement('div');
    row.className = 'echo-msg is-user';
    row.innerHTML =
      '<div class="echo-user-avatar">' + _escapeHtml(initial) + '</div>' +
      '<div>' +
        '<div class="echo-bubble">' + _escapeHtml(text) + '</div>' +
        '<div class="echo-time">' + _timeStr() + '</div>' +
      '</div>';
    messagesEl.appendChild(row);
    _scrollToBottom();
  }

  function _setLoading(loading) {
    isSending = loading;
    sendBtn.disabled = loading;
    typingEl.style.display = loading ? 'flex' : 'none';
    if (loading) _scrollToBottom();
  }

  function _scrollToBottom() {
    requestAnimationFrame(function () {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    });
  }

  function _autoResize() {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 140) + 'px';
  }

  function _clearChat() {
    sessionId = _newSessionId();
    history = [];
    messagesEl.innerHTML = '';
    _showWelcome();
    inputEl.focus();
  }

  // --- History ---
  function _openHistory() {
    historyPanel.style.display = 'block';
    sessionListEl.innerHTML = '<p class="echo-history-empty">加载中…</p>';
    _loadHistory();
  }

  function _t(key, fallback) {
    return (typeof SharedI18N !== 'undefined') ? SharedI18N.t(key) : fallback;
  }

  async function _loadHistory() {
    const token = localStorage.getItem('auth_token') || '';
    const participantCode = _getParticipantCode();
    const headers = {};
    if (token) headers['Authorization'] = 'Bearer ' + token;
    const url = '/api/emo-echo/sessions?participant_code=' + encodeURIComponent(participantCode);
    try {
      const res = await fetch(url, { headers: headers });
      if (!res.ok) throw new Error('API error ' + res.status);
      const data = await res.json();
      _renderSessionList(data.sessions || []);
    } catch (e) {
      sessionListEl.innerHTML = '<p class="echo-history-empty">' + _t('echo.historyFail', '加载失败，请稍后重试。') + '</p>';
    }
  }

  function _renderSessionList(sessions) {
    if (!sessions.length) {
      sessionListEl.innerHTML = '<p class="echo-history-empty">' + _t('echo.historyEmpty', '还没有历史对话记录。') + '</p>';
      return;
    }
    const lang = (typeof SharedI18N !== 'undefined') ? SharedI18N.lang() : 'zh';
    const locale = lang === 'en' ? 'en-US' : 'zh-CN';
    sessionListEl.innerHTML = '';
    sessions.forEach(function (s) {
      const d = new Date(s.last_active_at || s.created_at);
      const dateStr = d.toLocaleDateString(locale, { month: 'short', day: 'numeric' });
      const timeStr = d.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
      const preview = s.preview || '(空对话)';
      const count = s.message_count || 0;
      const item = document.createElement('div');
      item.className = 'echo-session-item';
      item.innerHTML =
        '<div class="echo-session-preview">' + _escapeHtml(preview) + '</div>' +
        '<div class="echo-session-meta">' + _escapeHtml(dateStr + ' ' + timeStr) + ' · ' + count + ' ' + _t('echo.msgCount', '条消息') + '</div>';
      item.addEventListener('click', function () { _restoreSession(s); });
      sessionListEl.appendChild(item);
    });
  }

  function _restoreSession(s) {
    const msgs = s.messages || [];
    sessionId = s.session_uuid;
    messagesEl.innerHTML = '';
    history = msgs.slice(-20).map(function (m) {
      return { role: m.role, content: m.content };
    });
    if (!msgs.length) {
      _showWelcome();
    } else {
      msgs.forEach(function (m) {
        if (m.role === 'user') _appendUserMsg(m.content);
        else _appendBotMsg(m.content);
      });
    }
    historyPanel.style.display = 'none';
    inputEl.focus();
  }

  // --- Utils ---
  function _newSessionId() {
    return 'echo-' + Date.now() + '-' + Math.random().toString(36).slice(2, 9);
  }

  function _getUserInitial() {
    try {
      const raw = localStorage.getItem('user_info');
      if (raw) {
        const info = JSON.parse(raw);
        const name = info.display_name || info.username || '';
        if (name) return name.charAt(0).toUpperCase();
      }
    } catch (e) { /* ignore */ }
    return '我';
  }

  function _timeStr() {
    const now = new Date();
    const h = String(now.getHours()).padStart(2, '0');
    const m = String(now.getMinutes()).padStart(2, '0');
    return h + ':' + m;
  }

  function _escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/\n/g, '<br>');
  }

  // --- Start ---
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
