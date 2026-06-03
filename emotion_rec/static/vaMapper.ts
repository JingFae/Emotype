export type EmotionQuadrant =
  | "high_negative"
  | "high_positive"
  | "low_negative"
  | "low_positive"
  | "neutral";

export type EmotionLexiconItem = {
  label: string;
  quadrant: EmotionQuadrant;
  valence: number;
  arousal: number;
};

export type VADInput = {
  valence?: number;
  arousal?: number;
  dominance?: number;
  confidence?: number;
  text?: string;
  explicit_label?: string;
  implicit_label?: string;
  evidence?: string[];
  source?: string;
};

export type EmotionLabelResult = {
  label: string;
  distance: number;
  confidence: number;
  nearest_label?: string;
};

export type EmotionCandidate = {
  label: string;
  valence: number;
  arousal: number;
  distance: number;
  confidence: number;
  quadrant: EmotionQuadrant;
  quadrant_label: string;
  color: string;
  source: string;
};

export type VAMapping = {
  valence: number;
  arousal: number;
  label: string;
  distance: number;
  confidence: number;
  label_confidence: number;
  source_confidence: number | null;
  quadrant: EmotionQuadrant;
  quadrant_label: string;
  color: string;
  nearest_label?: string;
  candidates: EmotionCandidate[];
};

export type SegmentMapping = VAMapping & {
  text: string;
  explicit_label?: string;
  implicit_label?: string;
  evidence?: string[];
  source?: string;
};

export const NEUTRAL_COLOR = "#94A3B8";
export const NEUTRAL_THRESHOLD = 0.12;
export const COMPLEX_DISTANCE_THRESHOLD = 0.38;
export const CONFIDENCE_DISTANCE_SCALE = 0.6;

export const ANCHOR_COLORS: Record<EmotionQuadrant, string> = {
  high_negative: "#DC2626",
  high_positive: "#F59E0B",
  low_negative: "#2563EB",
  low_positive: "#10B981",
  neutral: NEUTRAL_COLOR,
};

export const QUADRANT_LABELS: Record<EmotionQuadrant, string> = {
  high_negative: "消极高能量",
  high_positive: "积极高能量",
  low_negative: "消极低能量",
  low_positive: "积极低能量",
  neutral: "中性",
};

let emotionLexicon: EmotionLexiconItem[] = [];

export function createDefaultEmotionLexicon(): EmotionLexiconItem[] {
  const negativeValence = [-0.9, -0.7, -0.5, -0.3, -0.1];
  const positiveValence = [0.1, 0.3, 0.5, 0.7, 0.9];
  const highArousal = [0.9, 0.65, 0.4, 0.15];
  const lowArousal = [-0.15, -0.4, -0.65, -0.9];

  const groups: Array<{
    quadrant: EmotionQuadrant;
    xs: number[];
    ys: number[];
    labels: string[][];
  }> = [
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

export function clamp(value: number, lower = -1, upper = 1): number {
  if (!Number.isFinite(value)) return lower;
  return Math.max(lower, Math.min(upper, value));
}

export function normalizeVAD(
  raw: VADInput = {},
  sourceRange: "zero_one" | "zeroOne" | "minus_one_one" | "minusOneOne" = "zero_one",
): Required<Pick<VADInput, "valence" | "arousal" | "dominance">> {
  let valence = Number(raw.valence ?? 0);
  let arousal = Number(raw.arousal ?? 0);
  let dominance = Number(raw.dominance ?? 0);
  const source = sourceRange.replace(/[-_]/g, "").toLowerCase();

  if (source === "zeroone") {
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

function hexToRgb(color: string): [number, number, number] {
  const clean = color.replace("#", "");
  return [0, 2, 4].map((index) => Number.parseInt(clean.slice(index, index + 2), 16)) as [number, number, number];
}

function rgbToHex(rgb: number[]): string {
  return `#${rgb.map((channel) => Math.round(channel).toString(16).padStart(2, "0")).join("")}`.toUpperCase();
}

export function mixColor(start: string, end: string, amount: number): string {
  const ratio = clamp(amount, 0, 1);
  const startRgb = hexToRgb(start);
  const endRgb = hexToRgb(end);
  return rgbToHex(startRgb.map((channel, index) => channel + (endRgb[index] - channel) * ratio));
}

export function getQuadrant(valence: number, arousal: number): EmotionQuadrant {
  const v = clamp(valence);
  const a = clamp(arousal);
  if (Math.abs(v) < NEUTRAL_THRESHOLD && Math.abs(a) < NEUTRAL_THRESHOLD) return "neutral";
  if (v < 0 && a > 0) return "high_negative";
  if (v >= 0 && a > 0) return "high_positive";
  if (v < 0 && a <= 0) return "low_negative";
  return "low_positive";
}

export function getEmotionColor(valence: number, arousal: number): string {
  const quadrant = getQuadrant(valence, arousal);
  if (quadrant === "neutral") return NEUTRAL_COLOR;
  const distance = Math.sqrt(clamp(valence) ** 2 + clamp(arousal) ** 2);
  const strength = clamp(distance / Math.sqrt(2), 0, 1);
  return mixColor(NEUTRAL_COLOR, ANCHOR_COLORS[quadrant], strength);
}

export function getEmotionLexicon(): EmotionLexiconItem[] {
  if (!emotionLexicon.length) emotionLexicon = createDefaultEmotionLexicon();
  return emotionLexicon;
}

export function setEmotionLexicon(nextLexicon: EmotionLexiconItem[]): EmotionLexiconItem[] {
  emotionLexicon = Array.isArray(nextLexicon) && nextLexicon.length
    ? nextLexicon
    : createDefaultEmotionLexicon();
  return emotionLexicon;
}

export async function loadEmotionLexicon(url = "/shared/emotion_lexicon.json"): Promise<EmotionLexiconItem[]> {
  if (emotionLexicon.length) return emotionLexicon;
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error("lexicon request failed");
    return setEmotionLexicon(await response.json());
  } catch {
    return setEmotionLexicon(createDefaultEmotionLexicon());
  }
}

export function getEmotionLabel(valence: number, arousal: number): EmotionLabelResult {
  const v = clamp(valence);
  const a = clamp(arousal);
  if (getQuadrant(v, a) === "neutral") {
    return { label: "中性", distance: 0, confidence: 1 };
  }

  let nearest: EmotionLexiconItem | null = null;
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
      nearest_label: nearest?.label,
    };
  }

  return {
    label: nearest.label,
    distance: nearestDistance,
    confidence,
  };
}

export function getEmotionCandidates(valence: number, arousal: number, limit = 8): EmotionCandidate[] {
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

export function mapVA(input: VADInput | number, arousal?: number, confidence?: number): VAMapping {
  const raw = typeof input === "object" && input !== null
    ? input
    : { valence: input, arousal, confidence };
  const valence = clamp(Number(raw.valence ?? 0));
  const nextArousal = clamp(Number(raw.arousal ?? 0));
  const labelResult = getEmotionLabel(valence, nextArousal);
  const sourceConfidence = raw.confidence == null ? null : clamp(Number(raw.confidence), 0, 1);
  const finalConfidence = sourceConfidence == null
    ? labelResult.confidence
    : labelResult.confidence * sourceConfidence;
  const quadrant = getQuadrant(valence, nextArousal);

  return {
    valence,
    arousal: nextArousal,
    label: labelResult.label,
    distance: labelResult.distance,
    confidence: finalConfidence,
    label_confidence: labelResult.confidence,
    source_confidence: sourceConfidence,
    quadrant,
    quadrant_label: QUADRANT_LABELS[quadrant],
    color: getEmotionColor(valence, nextArousal),
    nearest_label: labelResult.nearest_label,
    candidates: getEmotionCandidates(valence, nextArousal),
  };
}

export function splitTextSegments(text: string): string[] {
  return String(text || "")
    .split(/[。！？!?，,；;\n]+/g)
    .map((segment) => segment.trim())
    .filter(Boolean);
}

export function mapSegments(segments: VADInput[] = []): { segments: SegmentMapping[]; overall: VAMapping } {
  const mappedSegments = segments.map((segment) => ({
    ...mapVA(segment),
    text: String(segment.text || "").trim(),
    explicit_label: segment.explicit_label,
    implicit_label: segment.implicit_label,
    evidence: segment.evidence,
    source: segment.source,
  }));

  let weightedValence = 0;
  let weightedArousal = 0;
  let totalWeight = 0;

  for (const segment of mappedSegments) {
    const weight = Math.max(1, segment.text.length) * Math.max(0.05, segment.confidence);
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
