(function attachVAMapper(global) {
  const NEUTRAL_COLOR = "#94A3B8";
  const NEUTRAL_THRESHOLD = 0.12;
  const COMPLEX_DISTANCE_THRESHOLD = 0.38;
  const CONFIDENCE_DISTANCE_SCALE = 0.6;

  const ANCHOR_COLORS = {
    high_negative: "#DC2626",
    high_positive: "#F59E0B",
    low_negative: "#2563EB",
    low_positive: "#10B981",
    neutral: NEUTRAL_COLOR,
  };

  const QUADRANT_LABELS = {
    high_negative: "消极高能量",
    high_positive: "积极高能量",
    low_negative: "消极低能量",
    low_positive: "积极低能量",
    neutral: "中性",
  };

  let emotionLexicon = [];

  function createDefaultEmotionLexicon() {
    const negativeValence = [-0.9, -0.7, -0.5, -0.3, -0.1];
    const positiveValence = [0.1, 0.3, 0.5, 0.7, 0.9];
    const highArousal = [0.9, 0.65, 0.4, 0.15];
    const lowArousal = [-0.15, -0.4, -0.65, -0.9];

    const groups = [
      {
        quadrant: "high_negative",
        xs: negativeValence,
        ys: highArousal,
        labels: [
          ["暴怒", "烦躁", "紧绷", "目瞪口呆", "很生气"],
          ["狂怒", "懊恼", "紧张", "坐立不安", "愤怒"],
          ["害怕", "生气", "焦虑", "忧虑", "担心"],
          ["憎恶", "恼火", "不耐烦", "不安", "不高兴"],
        ],
      },
      {
        quadrant: "high_positive",
        xs: positiveValence,
        ys: highArousal,
        labels: [
          ["惊讶", "乐观", "激动人心", "狂喜", "兴奋"],
          ["欢快", "积极", "兴高采烈", "精力充沛", "活跃"],
          ["热情", "激动", "满意的", "开心", "专注"],
          ["自豪", "愉快", "快乐", "满怀希望", "幸福"],
        ],
      },
      {
        quadrant: "low_negative",
        xs: negativeValence,
        ys: lowArousal,
        labels: [
          ["厌恶", "闷闷不乐", "失望", "低落", "冷漠"],
          ["消极", "忧郁", "挫败", "悲伤", "无聊"],
          ["疏离", "孤独", "疲惫", "沮丧", "抑郁"],
          ["耗尽", "厌倦", "绝望", "凄凉", "精疲力竭"],
        ],
      },
      {
        quadrant: "low_positive",
        xs: positiveValence,
        ys: lowArousal,
        labels: [
          ["安逸", "悠闲", "满足", "爱意", "自信感"],
          ["冷静", "安全", "满意", "感恩", "有成就感"],
          ["放松", "松弛", "安宁", "平衡", "自在"],
          ["平静", "舒适", "无忧无虑", "惬意", "安详"],
        ],
      },
    ];

    return groups.flatMap((group) =>
      group.labels.flatMap((row, rowIndex) =>
        row.map((label, colIndex) => ({
          label,
          quadrant: group.quadrant,
          valence: group.xs[colIndex],
          arousal: group.ys[rowIndex],
        })),
      ),
    );
  }

  function clamp(value, lower = -1, upper = 1) {
    const number = Number(value);
    if (!Number.isFinite(number)) return lower;
    return Math.max(lower, Math.min(upper, number));
  }

  function normalizeVAD(raw = {}, sourceRange = "zero_one") {
    let valence = Number(raw.valence ?? 0);
    let arousal = Number(raw.arousal ?? 0);
    let dominance = Number(raw.dominance ?? 0);
    const source = String(sourceRange).replace(/[-_]/g, "").toLowerCase();

    if (source === "zeroone" || source === "01") {
      valence = valence * 2 - 1;
      arousal = arousal * 2 - 1;
      dominance = dominance * 2 - 1;
    }

    return {
      valence: clamp(valence),
      arousal: clamp(arousal),
      dominance: clamp(dominance),
    };
  }

  function hexToRgb(color) {
    const clean = String(color).replace("#", "");
    return [0, 2, 4].map((index) => Number.parseInt(clean.slice(index, index + 2), 16));
  }

  function rgbToHex(rgb) {
    return `#${rgb.map((channel) => Math.round(channel).toString(16).padStart(2, "0")).join("")}`.toUpperCase();
  }

  function mixColor(start, end, amount) {
    const ratio = clamp(amount, 0, 1);
    const startRgb = hexToRgb(start);
    const endRgb = hexToRgb(end);
    return rgbToHex(startRgb.map((channel, index) => channel + (endRgb[index] - channel) * ratio));
  }

  function getQuadrant(valence, arousal) {
    const v = clamp(valence);
    const a = clamp(arousal);
    if (Math.abs(v) < NEUTRAL_THRESHOLD && Math.abs(a) < NEUTRAL_THRESHOLD) return "neutral";
    if (v < 0 && a > 0) return "high_negative";
    if (v >= 0 && a > 0) return "high_positive";
    if (v < 0 && a <= 0) return "low_negative";
    return "low_positive";
  }

  function getEmotionColor(valence, arousal) {
    const quadrant = getQuadrant(valence, arousal);
    if (quadrant === "neutral") return NEUTRAL_COLOR;
    const distance = Math.sqrt(clamp(valence) ** 2 + clamp(arousal) ** 2);
    const strength = clamp(distance / Math.sqrt(2), 0, 1);
    return mixColor(NEUTRAL_COLOR, ANCHOR_COLORS[quadrant], strength);
  }

  function getEmotionLexicon() {
    if (!emotionLexicon.length) emotionLexicon = createDefaultEmotionLexicon();
    return emotionLexicon;
  }

  function setEmotionLexicon(nextLexicon) {
    emotionLexicon = Array.isArray(nextLexicon) && nextLexicon.length
      ? nextLexicon
      : createDefaultEmotionLexicon();
    return emotionLexicon;
  }

  async function loadEmotionLexicon(url = "/shared/emotion_lexicon.json") {
    if (emotionLexicon.length) return emotionLexicon;
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error("lexicon request failed");
      const data = await response.json();
      return setEmotionLexicon(data);
    } catch (error) {
      return setEmotionLexicon(createDefaultEmotionLexicon());
    }
  }

  function getEmotionLabel(valence, arousal) {
    const v = clamp(valence);
    const a = clamp(arousal);
    if (getQuadrant(v, a) === "neutral") {
      return { label: "中性", distance: 0, confidence: 1 };
    }

    let nearest = null;
    let nearestDistance = Number.POSITIVE_INFINITY;
    for (const item of getEmotionLexicon()) {
      const distance = Math.sqrt((v - item.valence) ** 2 + (a - item.arousal) ** 2);
      if (distance < nearestDistance) {
        nearest = item;
        nearestDistance = distance;
      }
    }

    const confidence = clamp(1 - nearestDistance / CONFIDENCE_DISTANCE_SCALE, 0, 1);
    if (!nearest || nearestDistance > COMPLEX_DISTANCE_THRESHOLD) {
      return {
        label: "复杂情绪",
        distance: nearestDistance,
        confidence,
        nearest_label: nearest ? nearest.label : undefined,
      };
    }

    return {
      label: nearest.label,
      distance: nearestDistance,
      confidence,
    };
  }

  function getEmotionCandidates(valence, arousal, limit = 8) {
    const v = clamp(valence);
    const a = clamp(arousal);
    const candidates = getEmotionLexicon()
      .map((item) => {
        const distance = Math.sqrt((v - item.valence) ** 2 + (a - item.arousal) ** 2);
        const confidence = clamp(1 - distance / CONFIDENCE_DISTANCE_SCALE, 0, 1);
        const quadrant = item.quadrant || getQuadrant(item.valence, item.arousal);
        return {
          label: item.label,
          valence: clamp(item.valence),
          arousal: clamp(item.arousal),
          distance,
          confidence,
          quadrant,
          quadrant_label: QUADRANT_LABELS[quadrant],
          color: getEmotionColor(item.valence, item.arousal),
          source: "lexicon_nearby",
        };
      })
      .sort((left, right) => left.distance - right.distance)
      .slice(0, Math.max(1, Number(limit) || 8));

    if (getQuadrant(v, a) === "neutral") {
      candidates.unshift({
        label: "中性",
        valence: v,
        arousal: a,
        distance: 0,
        confidence: 1,
        quadrant: "neutral",
        quadrant_label: QUADRANT_LABELS.neutral,
        color: NEUTRAL_COLOR,
        source: "neutral_center",
      });
    }

    return candidates.slice(0, Math.max(1, Number(limit) || 8));
  }

  function mapVA(input, arousal, confidence) {
    const raw = typeof input === "object" && input !== null
      ? input
      : { valence: input, arousal, confidence };
    const valence = clamp(raw.valence ?? 0);
    const nextArousal = clamp(raw.arousal ?? 0);
    const labelResult = getEmotionLabel(valence, nextArousal);
    const labelConfidence = Number(labelResult.confidence);
    const sourceConfidence = raw.confidence == null ? null : clamp(raw.confidence, 0, 1);
    const finalConfidence = sourceConfidence == null
      ? labelConfidence
      : labelConfidence * sourceConfidence;
    const quadrant = getQuadrant(valence, nextArousal);

    return {
      valence,
      arousal: nextArousal,
      label: labelResult.label,
      distance: Number(labelResult.distance),
      confidence: finalConfidence,
      label_confidence: labelConfidence,
      source_confidence: sourceConfidence,
      quadrant,
      quadrant_label: QUADRANT_LABELS[quadrant],
      color: getEmotionColor(valence, nextArousal),
      nearest_label: labelResult.nearest_label,
      candidates: getEmotionCandidates(valence, nextArousal),
    };
  }

  function splitTextSegments(text) {
    return String(text || "")
      .split(/[。！？!?，,；;\n]+/g)
      .map((segment) => segment.trim())
      .filter(Boolean);
  }

  function mapSegments(segments = []) {
    const mappedSegments = segments.map((segment) => ({
      ...mapVA(segment),
      text: String(segment.text || "").trim(),
    }));

    let weightedValence = 0;
    let weightedArousal = 0;
    let totalWeight = 0;

    for (const segment of mappedSegments) {
      const weight = Math.max(1, segment.text.length) * Math.max(0.05, Number(segment.confidence));
      weightedValence += segment.valence * weight;
      weightedArousal += segment.arousal * weight;
      totalWeight += weight;
    }

    const overall = totalWeight
      ? mapVA({
          valence: weightedValence / totalWeight,
          arousal: weightedArousal / totalWeight,
          confidence: mappedSegments.reduce((sum, item) => sum + item.confidence, 0) / mappedSegments.length,
        })
      : mapVA({ valence: 0, arousal: 0, confidence: 0 });

    return { segments: mappedSegments, overall };
  }

  global.VAMapper = {
    NEUTRAL_COLOR,
    ANCHOR_COLORS,
    QUADRANT_LABELS,
    createDefaultEmotionLexicon,
    loadEmotionLexicon,
    getEmotionLexicon,
    setEmotionLexicon,
    normalizeVAD,
    getQuadrant,
    getEmotionColor,
    getEmotionLabel,
    getEmotionCandidates,
    mapVA,
    splitTextSegments,
    mapSegments,
    mixColor,
  };
})(window);
