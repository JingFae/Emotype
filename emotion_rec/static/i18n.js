/**
 * EmoBridge Shared i18n Module
 * Reads language from localStorage("emomirror.lang") and applies translations
 * to all elements with [data-i18n] attributes.
 */
(function (global) {
  "use strict";

  var I18N = {
    zh: {
      // Navigation (all pages)
      "nav.home": "首页", "nav.journal": "随手记", "nav.diaryBook": "日记本",
      "nav.review": "情绪复盘", "nav.records": "历史记录", "nav.body": "身体感受",
      "nav.data": "数据", "nav.profile": "个人信息", "nav.login": "登录",
      "nav.essay": "情绪随笔", "nav.ecoEcho": "Emo 回响", "nav.historyReview": "历史回顾",

      // Emo Echo (chatbox) page
      "echo.eyebrow": "AI 情感伴侣", "echo.title": "Emo 回响",
      "echo.tagline": "心事诉说，情绪皆有回响",
      "echo.historyBtn": "历史记录", "echo.clearBtn": "新对话",
      "echo.panelTitle": "历史对话", "echo.panelClose": "关闭",
      "echo.historyEmpty": "还没有历史对话记录。",
      "echo.historyLoading": "加载中…", "echo.historyFail": "加载失败，请稍后重试。",
      "echo.inputPh": "写下你想说的…（Enter 发送，Shift+Enter 换行）",
      "echo.disclaimer": "Emo 回响是情感陪伴助手，不提供心理诊断或医疗建议。",
      "echo.msgCount": "条消息", "echo.fallback": "抱歉，我现在有点走神了，等一下再试试吧。",

      // History Review page
      "hr.tabReview": "情绪回顾", "hr.tabRecords": "历史记录",
      "hr.dataEyebrow": "Data & Insights", "hr.dataTitle": "情绪数据",
      "hr.emotionFreq": "情绪频率分布", "hr.refresh": "刷新",
      "hr.vaHistory": "V-A 坐标历史", "hr.noData": "暂无记录，先去写日记吧 ✏️",
      "hr.summaryTitle": "记录摘要", "hr.exportTitle": "导出数据",
      "hr.exportJson": "导出 JSON", "hr.exportCsv": "导出 CSV", "hr.clearAll": "清除所有记录",
      "hr.recordsEyebrow": "Timeline", "hr.recordsTitle": "记录列表",

      // Profile page
      "profile.eyebrow": "My Profile", "profile.title": "个人信息",
      "profile.settingsEyebrow": "Settings", "profile.settingsTitle": "账户设置",
      "profile.displayName": "显示名", "profile.displayNamePh": "修改显示名",
      "profile.currentPw": "当前密码", "profile.currentPwPh": "输入当前密码以修改",
      "profile.newPw": "新密码", "profile.newPwPh": "输入新密码（至少4位）",
      "profile.save": "保存修改",
      "profile.lang": "语言偏好", "profile.localMode": "本地模式",
      "profile.localModeHint": "仅保存在本地浏览器，不同步到服务器",
      "profile.quickEyebrow": "Quick Access", "profile.quickTitle": "我的数据",
      "profile.adminEyebrow": "Admin", "profile.adminTitle": "用户管理",
      "profile.thUsername": "用户名", "profile.thDisplay": "显示名", "profile.thRole": "角色",
      "profile.thCreated": "注册时间", "profile.thLastLogin": "最后登录", "profile.thActions": "操作",
      "profile.viewRecords": "查看记录", "profile.exportJson": "导出JSON", "profile.exportCsv": "导出CSV",
      "profile.close": "关闭", "profile.thSource": "来源", "profile.thDate": "日期", "profile.thSummary": "内容摘要",
      "profile.roleAdmin": "管理员", "profile.roleUser": "用户",

      // Diary page
      "diary.eyebrow": "Diary", "diary.title": "日记本",
      "diary.date": "日期", "diary.refreshContext": "查看今日情绪记录",
      "diary.contextEyebrow": "素材", "diary.contextTitle": "今日情绪记录",
      "diary.insertContext": "插入选中摘要",
      "diary.physicalWeather": "现实天气", "diary.moodWeather": "心情天气",
      "diary.entryTitle": "标题", "diary.entryTitlePh": "给今天留一个标题",
      "diary.content": "正式日记",
      "diary.contentPh": "完整写下今天发生的事、你的反应、身体感受和想留下来的细节。",
      "diary.voice": "语音转文字", "diary.reflect": "更新复盘", "diary.save": "保存日记",
      "diary.reviewEyebrow": "Review", "diary.reviewTitle": "AI 复盘",
      "diary.vaLabel": "V-A 坐标",
      "diary.emotionColor": "情绪颜色", "diary.secondaryEmotion": "二级情绪",
      "diary.fineEmotion": "细粒度情绪", "diary.bodySignal": "身体信号",
      "va.positive": "积极", "va.negative": "消极", "va.high": "高能量", "va.low": "低能量",
      "diary.weatherSunny": "晴朗", "diary.weatherCloudy": "多云", "diary.weatherOvercast": "阴天",
      "diary.weatherRainy": "下雨", "diary.weatherStormy": "暴风雨", "diary.weatherSnowy": "下雪",
      "diary.weatherWindy": "有风", "diary.weatherFoggy": "有雾",

      // Review page
      "review.eyebrow": "Emotion Review", "review.title": "情绪复盘",
      "review.startDate": "开始", "review.endDate": "结束",
      "review.loadStats": "查看统计", "review.reflect": "生成复盘",
      "review.totalLabel": "记录总数", "review.period7d": "近 7 天",
      "review.journalLabel": "随手记", "review.diaryLabel": "正式日记", "review.bodyLabel": "身体感受",
      "review.trendEyebrow": "Trend", "review.trendTitle": "情绪趋势", "review.loading": "载入中",
      "review.trendEmpty": "这段时间还没有可绘制的 V-A 数据。",
      "review.dayEyebrow": "Daily Mix", "review.dayTitle": "情绪分布",
      "review.selectDay": "选择日期",
      "review.dayEmpty": "这一天记录还不多，暂时看不出明显分布。",
      "review.paletteEyebrow": "Palette", "review.paletteTitle": "情绪颜色色板",
      "review.emotionEyebrow": "Emotions", "review.emotionTitle": "主要情绪",
      "review.fineEyebrow": "Fine", "review.fineTitle": "细粒度情绪",
      "review.triggerEyebrow": "Signals", "review.triggerTitle": "触发因素摘要",
      "review.bodySignalEyebrow": "Body", "review.bodySignalTitle": "身体信号摘要",
      "review.sourceEyebrow": "Sources", "review.sourceTitle": "记录来源明细",
      "review.aiEyebrow": "AI Review", "review.aiTitle": "阶段性回顾",
      "review.aiNotGenerated": "未生成",
      "review.aiTriggerLabel": "可能触发", "review.aiBodyLabel": "身体线索",
      "review.aiQuestionLabel": "可以继续问自己", "review.aiStepLabel": "很小的一步",
      "review.aiDisclaimer": "这份复盘只是帮助整理线索，不用于诊断。",

      // Records page
      "records.eyebrow": "Timeline", "records.title": "历史记录",
      "records.startDate": "开始", "records.endDate": "结束",
      "records.source": "来源", "records.sourceAll": "全部",
      "records.load": "查询记录", "records.totalLabel": "记录总数",
      "records.listEyebrow": "Timeline", "records.listTitle": "记录列表",
      "records.noRecords": "暂无记录",

      // Body sensation page
      "body.eyebrow": "Emotion & Body", "body.title": "身体感受",
      "body.subtitle": "选择身体部位和感受，系统会结合最近记录生成温和、非诊断式的缓解提示。",
      "body.refreshContext": "读取最近记录",
      "body.mapEyebrow": "Body Map", "body.mapTitle": "身体部位",
      "body.selectedTitle": "已选组合", "body.noPairs": "暂无",
      "body.contextEyebrow": "Context", "body.contextTitle": "当前记录参考",
      "body.contextNotLoaded": "未读取",
      "body.contextPh": "可以粘贴今天的随手记、正式日记片段，或留空让系统只根据本次身体感受生成建议。",
      "body.regionEyebrow": "Region", "body.regionTitle": "选择部位",
      "body.symptomEyebrow": "Sensation", "body.symptomTitle": "选择感受",
      "body.severity": "程度", "body.duration": "持续时间",
      "body.freeText": "补充描述",
      "body.freeTextPh": "例如：今天喝水较少、久坐、睡眠不足，或某个时段更明显。",
      "body.addPair": "加入组合", "body.clearPairs": "清空",
      "body.generate": "生成身体感受建议",
      "body.statusHint": "系统会综合身体感受和最近记录。",
      "body.adviceEyebrow": "Advice", "body.adviceTitle": "建议",
      "body.advicePending": "待生成",
      "body.adviceEmpty": "选择至少一个身体感受组合后生成建议。建议会保持温和、非诊断式，并保留必要的就医提醒。",
    },
    en: {
      // Navigation (all pages)
      "nav.home": "Home", "nav.journal": "Journal", "nav.diaryBook": "Diary",
      "nav.review": "Review", "nav.records": "Records", "nav.body": "Body Sense",
      "nav.data": "Data", "nav.profile": "Profile", "nav.login": "Login",
      "nav.essay": "Journal", "nav.ecoEcho": "Emo Echo", "nav.historyReview": "History",

      // Emo Echo (chatbox) page
      "echo.eyebrow": "AI Companion", "echo.title": "Emo Echo",
      "echo.tagline": "Share your thoughts, emotions find their echo",
      "echo.historyBtn": "History", "echo.clearBtn": "New Chat",
      "echo.panelTitle": "Chat History", "echo.panelClose": "Close",
      "echo.historyEmpty": "No previous conversations yet.",
      "echo.historyLoading": "Loading…", "echo.historyFail": "Failed to load. Please try again.",
      "echo.inputPh": "Write what's on your mind… (Enter to send, Shift+Enter for new line)",
      "echo.disclaimer": "Emo Echo is an emotional companion and does not provide psychological diagnosis or medical advice.",
      "echo.msgCount": "messages", "echo.fallback": "Sorry, I got a little distracted. Please try again.",

      // History Review page
      "hr.tabReview": "Emotion Review", "hr.tabRecords": "Records",
      "hr.dataEyebrow": "Data & Insights", "hr.dataTitle": "Emotion Data",
      "hr.emotionFreq": "Emotion Frequency", "hr.refresh": "Refresh",
      "hr.vaHistory": "V-A Coordinate History", "hr.noData": "No records yet. Start writing! ✏️",
      "hr.summaryTitle": "Summary", "hr.exportTitle": "Export Data",
      "hr.exportJson": "Export JSON", "hr.exportCsv": "Export CSV", "hr.clearAll": "Clear All Records",
      "hr.recordsEyebrow": "Timeline", "hr.recordsTitle": "Record List",

      // Profile page
      "profile.eyebrow": "My Profile", "profile.title": "Profile",
      "profile.settingsEyebrow": "Settings", "profile.settingsTitle": "Account Settings",
      "profile.displayName": "Display Name", "profile.displayNamePh": "Change display name",
      "profile.currentPw": "Current Password", "profile.currentPwPh": "Enter current password",
      "profile.newPw": "New Password", "profile.newPwPh": "Enter new password (min 4 chars)",
      "profile.save": "Save Changes",
      "profile.lang": "Language", "profile.localMode": "Local Mode",
      "profile.localModeHint": "Save locally only, no server sync",
      "profile.quickEyebrow": "Quick Access", "profile.quickTitle": "My Data",
      "profile.adminEyebrow": "Admin", "profile.adminTitle": "User Management",
      "profile.thUsername": "Username", "profile.thDisplay": "Display Name", "profile.thRole": "Role",
      "profile.thCreated": "Created", "profile.thLastLogin": "Last Login", "profile.thActions": "Actions",
      "profile.viewRecords": "View Records", "profile.exportJson": "Export JSON", "profile.exportCsv": "Export CSV",
      "profile.close": "Close", "profile.thSource": "Source", "profile.thDate": "Date", "profile.thSummary": "Summary",
      "profile.roleAdmin": "Admin", "profile.roleUser": "User",

      // Diary page
      "diary.eyebrow": "Diary", "diary.title": "Diary Book",
      "diary.date": "Date", "diary.refreshContext": "View today's entries",
      "diary.contextEyebrow": "Material", "diary.contextTitle": "Today's Emotion Records",
      "diary.insertContext": "Insert selected excerpt",
      "diary.physicalWeather": "Weather", "diary.moodWeather": "Mood Weather",
      "diary.entryTitle": "Title", "diary.entryTitlePh": "Give today a title",
      "diary.content": "Formal Diary",
      "diary.contentPh": "Write about what happened today, your reactions, body sensations, and details you want to keep.",
      "diary.voice": "Voice to Text", "diary.reflect": "Update Reflection", "diary.save": "Save Diary",
      "diary.reviewEyebrow": "Review", "diary.reviewTitle": "AI Reflection",
      "diary.vaLabel": "V-A Coordinate",
      "diary.emotionColor": "Emotion Color", "diary.secondaryEmotion": "Secondary Emotions",
      "diary.fineEmotion": "Fine-grained Emotions", "diary.bodySignal": "Body Signals",
      "va.positive": "Positive", "va.negative": "Negative", "va.high": "High energy", "va.low": "Low energy",
      "diary.weatherSunny": "Sunny", "diary.weatherCloudy": "Cloudy", "diary.weatherOvercast": "Overcast",
      "diary.weatherRainy": "Rainy", "diary.weatherStormy": "Stormy", "diary.weatherSnowy": "Snowy",
      "diary.weatherWindy": "Windy", "diary.weatherFoggy": "Foggy",

      // Review page
      "review.eyebrow": "Emotion Review", "review.title": "Emotion Review",
      "review.startDate": "Start", "review.endDate": "End",
      "review.loadStats": "View Stats", "review.reflect": "Generate Review",
      "review.totalLabel": "Total entries", "review.period7d": "Last 7 days",
      "review.journalLabel": "Journal", "review.diaryLabel": "Diary", "review.bodyLabel": "Body",
      "review.trendEyebrow": "Trend", "review.trendTitle": "Emotion Trend", "review.loading": "Loading",
      "review.trendEmpty": "No V-A data to plot for this period.",
      "review.dayEyebrow": "Daily Mix", "review.dayTitle": "Emotion Distribution",
      "review.selectDay": "Select day",
      "review.dayEmpty": "Not enough records for this day to show a clear distribution.",
      "review.paletteEyebrow": "Palette", "review.paletteTitle": "Emotion Color Palette",
      "review.emotionEyebrow": "Emotions", "review.emotionTitle": "Primary Emotions",
      "review.fineEyebrow": "Fine", "review.fineTitle": "Fine-grained Emotions",
      "review.triggerEyebrow": "Signals", "review.triggerTitle": "Trigger Summary",
      "review.bodySignalEyebrow": "Body", "review.bodySignalTitle": "Body Signal Summary",
      "review.sourceEyebrow": "Sources", "review.sourceTitle": "Record Source Details",
      "review.aiEyebrow": "AI Review", "review.aiTitle": "Period Review",
      "review.aiNotGenerated": "Not generated",
      "review.aiTriggerLabel": "Possible triggers", "review.aiBodyLabel": "Body clues",
      "review.aiQuestionLabel": "Questions to ask yourself", "review.aiStepLabel": "A small step",
      "review.aiDisclaimer": "This review helps organize clues. Not for diagnosis.",

      // Records page
      "records.eyebrow": "Timeline", "records.title": "History Records",
      "records.startDate": "Start", "records.endDate": "End",
      "records.source": "Source", "records.sourceAll": "All",
      "records.load": "Load Records", "records.totalLabel": "Total entries",
      "records.listEyebrow": "Timeline", "records.listTitle": "Record List",
      "records.noRecords": "No records found",

      // Body sensation page
      "body.eyebrow": "Emotion & Body", "body.title": "Body Sensation",
      "body.subtitle": "Select body regions and sensations. The system combines them with recent records to generate gentle, non-diagnostic advice.",
      "body.refreshContext": "Load recent records",
      "body.mapEyebrow": "Body Map", "body.mapTitle": "Body Regions",
      "body.selectedTitle": "Selected pairs", "body.noPairs": "None yet",
      "body.contextEyebrow": "Context", "body.contextTitle": "Current Record Reference",
      "body.contextNotLoaded": "Not loaded",
      "body.contextPh": "Paste today's journal or diary excerpt, or leave blank to generate advice based only on body sensations.",
      "body.regionEyebrow": "Region", "body.regionTitle": "Select Region",
      "body.symptomEyebrow": "Sensation", "body.symptomTitle": "Select Sensation",
      "body.severity": "Severity", "body.duration": "Duration",
      "body.freeText": "Additional notes",
      "body.freeTextPh": "e.g., drank little water today, sat for a long time, poor sleep, or more noticeable at certain times.",
      "body.addPair": "Add pair", "body.clearPairs": "Clear",
      "body.generate": "Generate Body Advice",
      "body.statusHint": "System combines body sensations with recent records.",
      "body.adviceEyebrow": "Advice", "body.adviceTitle": "Advice",
      "body.advicePending": "Pending",
      "body.adviceEmpty": "Select at least one body sensation pair to generate advice. Advice remains gentle, non-diagnostic, and includes necessary medical reminders.",
    }
  };

  function getCurrentLang() {
    try { return localStorage.getItem("emomirror.lang") || "zh"; } catch (e) { return "zh"; }
  }

  function t(key) {
    var lang = getCurrentLang();
    return (I18N[lang] || I18N.zh)[key] || (I18N.zh)[key] || key;
  }

  function applySharedI18n() {
    var lang = getCurrentLang();
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var key = el.getAttribute("data-i18n");
      if (key) el.textContent = t(key);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(function (el) {
      var key = el.getAttribute("data-i18n-placeholder");
      if (key) el.placeholder = t(key);
    });
  }

  // Auto-apply on DOMContentLoaded
  function init() {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", applySharedI18n);
    } else {
      applySharedI18n();
    }
  }

  global.SharedI18N = { t: t, apply: applySharedI18n, lang: getCurrentLang };
  init();
})(window);
