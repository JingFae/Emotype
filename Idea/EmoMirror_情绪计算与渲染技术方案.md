# EmoMirror 情绪计算与动态排版技术方案

## 1. 核心判断

EmoMirror 的目标不是简单识别显性情绪词，而是帮助用户看见文本和语音中隐性蕴含的情绪状态。

因此系统不应把 LLM、V-A 映射、情绪标签、视觉渲染混在一起。更合理的架构是：

```text
输入层
文本输入 / ASR 转写 / 原始语音

→ 语义情绪解析层
识别显性情绪、隐性情绪、身体线索、转折、否认、强撑表达

→ V-A 值解析层
输出 segment-level valence / arousal / confidence / evidence

→ 情绪标签推断层
融合语义证据、V-A 坐标、上下文冲突和置信度，输出 top-k emotion labels

→ V-A 映射层
将 V-A 值映射为颜色、象限、强度、距离和基础渲染参数

→ 动态排版渲染层
根据颜色、标签、唤醒度、复杂度和置信度生成 kinetic typography
```

一句话原则：

```text
语义模型负责理解，
V-A mapper 负责连续情绪空间，
标签层负责解释，
渲染层负责表达。
```

## 2. 当前项目状态

### 2.1 文本输入路径

当前 `/analyze-text` 的 typed text 情绪识别不是语义模型，也不是 LLM 分类，而是：

```text
用户输入文本
→ 按标点分句
→ 本地情绪词典 / 英文 hint 匹配
→ 得到粗略 valence / arousal / confidence
→ va_mapper.py 生成 label / color / quadrant / confidence
→ LLM 只负责 llm_design 动态排版
```

当前优点：

- 可控、稳定、快速。
- 不依赖外部 API 也能运行。
- 适合作为 demo 和 fallback。

当前不足：

- 只能识别显性词，如“生气”“开心”“sad”“happy”。
- 对隐性情绪理解不足，如“我说没事，但胸口很紧”。
- 当前标签主要来自 V-A 最近点，解释性有限。
- 如果 LLM 排版 API 卡住，视觉生成会延迟，但情绪映射本身并不是 LLM 完成的。

### 2.2 语音输入路径

当前 `/predict` 使用本地 Wav2Vec2 emotion model：

```text
上传音频
→ pydub / librosa 转 16k mono wav
→ Wav2Vec2Processor
→ EmotionModel
→ 输出 arousal / dominance / valence
→ normalize_vad 转换到 [-1, 1]
→ va_mapper.py 生成 va_mapping
→ LLM 或 fallback 生成 llm_design
```

语音模型更适合捕捉：

- 唤醒度 arousal
- 紧张、激动、压抑、疲惫等声学状态
- 能量、音高等 acoustic features

语音模型不擅长单独判断：

- 复杂语义
- 事件意义
- 人际关系中的委屈、羞耻、被否定感

## 3. 理想模块划分

### 3.1 ASR 模块

职责：

- 将语音转成文本。
- 输出 transcript、时间戳、ASR confidence。

不负责：

- 情绪分类。
- V-A 映射。
- 动态排版。

建议输出：

```json
{
  "text": "我没事，只是胸口有点紧。",
  "segments": [
    {
      "text": "我没事",
      "start": 0.0,
      "end": 1.2,
      "confidence": 0.91
    },
    {
      "text": "只是胸口有点紧",
      "start": 1.3,
      "end": 3.4,
      "confidence": 0.88
    }
  ]
}
```

### 3.2 Text Emotion 模块

建议新增：

```text
emotion_rec/text_emotion.py
```

职责：

- 识别文本中的显性与隐性情绪。
- 输出每个 segment 的 V-A 值、候选标签和证据。

输入：

```json
{
  "text": "没事，我真的没事，只是胸口有点紧。",
  "segments": ["没事", "我真的没事", "只是胸口有点紧"]
}
```

输出：

```json
{
  "segments": [
    {
      "text": "没事",
      "valence": -0.15,
      "arousal": 0.25,
      "confidence": 0.42,
      "explicit_label": "中性",
      "implicit_label": "回避",
      "evidence": ["否认式表达"]
    },
    {
      "text": "只是胸口有点紧",
      "valence": -0.45,
      "arousal": 0.65,
      "confidence": 0.78,
      "explicit_label": "不安",
      "implicit_label": "焦虑",
      "evidence": ["身体紧绷", "弱化表达：只是"]
    }
  ]
}
```

### 3.3 Audio Emotion 模块

当前可继续使用 Wav2Vec2 emotion model。

职责：

- 从音频中推断 acoustic VAD。
- 提供 pitch、energy、tempo 等声学特征。

建议输出：

```json
{
  "valence": -0.25,
  "arousal": 0.72,
  "dominance": 0.31,
  "confidence": 0.68,
  "acoustics": {
    "pitch_norm": 0.61,
    "energy_norm": 0.74
  }
}
```

### 3.4 Fusion 模块

建议新增：

```text
emotion_rec/emotion_fusion.py
```

职责：

- 融合文本语义情绪和语音声学情绪。
- 根据 ASR confidence、音频质量、文本长度动态调权。

推荐初始规则：

```text
valence = 0.65 * text_valence + 0.35 * audio_valence
arousal = 0.35 * text_arousal + 0.65 * audio_arousal
```

原因：

- 文本更适合判断情绪效价 valence。
- 语音更适合判断唤醒度 arousal。
- 如果 ASR 置信度低，降低 text 权重。
- 如果音频很短或噪声大，降低 audio 权重。

### 3.5 VA Mapper 模块

当前已有：

```text
emotion_rec/va_mapper.py
emotion_rec/shared/emotion_lexicon.json
```

职责：

- 接收已经得到的 valence / arousal。
- 输出 color、quadrant、nearest label、distance、confidence。

不负责：

- 调用 LLM。
- 调用 ASR。
- 判断文本语义。
- 训练或执行情绪识别模型。

当前规则适合作为基础映射层，但标签层需要继续升级。

### 3.6 Label Inference 模块

建议新增：

```text
emotion_rec/emotion_labeler.py
```

当前问题：

```text
只根据 V-A 最近点找标签
```

这个逻辑过于粗糙，因为不同情绪可能 V-A 坐标相近，但语义差异很大。

例如：

- 焦虑、害怕、紧张都可能是负效价高唤醒。
- 委屈、羞耻、内疚可能 V-A 接近，但语义结构不同。
- 平静、麻木、压抑都可能低唤醒，但情绪含义完全不同。

推荐标签评分：

```text
label_score =
  0.45 * semantic_label_probability
+ 0.35 * VA_prototype_similarity
+ 0.15 * appraisal_feature_match
+ 0.05 * context_consistency
```

标签输出建议：

```json
{
  "primary": "焦虑",
  "top_k": [
    { "label": "焦虑", "score": 0.78 },
    { "label": "不安", "score": 0.71 },
    { "label": "压抑", "score": 0.54 }
  ],
  "is_complex": true,
  "explanation": [
    "文本出现身体紧绷线索",
    "前文存在否认式表达",
    "V-A 位于消极高唤醒区域"
  ]
}
```

## 4. 隐性情绪识别应该看什么

### 4.1 身体线索

典型表达：

- 胸口紧
- 呼吸不过来
- 胃不舒服
- 睡不着
- 手抖
- 头很重
- 眼眶酸

可能对应：

- 焦虑
- 压抑
- 恐惧
- 悲伤
- 紧张

### 4.2 否认和弱化表达

典型表达：

- 没事
- 还好
- 也没什么
- 我不在意
- 只是有点
- 可能是我想多了

可能对应：

- 回避
- 压抑
- 自我否定
- 情绪隔离

### 4.3 转折结构

典型表达：

- 但是
- 可是
- 其实
- 不过
- 虽然

分析重点：

```text
转折后的内容通常比转折前更接近真实情绪。
```

例子：

```text
我觉得还好，但是回家路上一直很想哭。
```

应更重视：

```text
回家路上一直很想哭
```

### 4.4 关系和评价线索

典型表达：

- 被忽视
- 被否定
- 被误解
- 不被需要
- 没有人听我说
- 我是不是太麻烦了

可能对应：

- 委屈
- 羞耻
- 孤独
- 失落
- 愤怒

### 4.5 行为冲动

典型表达：

- 想逃走
- 不想回复
- 想删掉
- 想哭
- 想大喊
- 什么都不想做

可能对应：

- 恐惧
- 愤怒
- 抑郁
- 疲惫
- 无助

## 5. 推荐模型路线

### 5.1 第一阶段：规则 + LLM 离线标注

目标：

- 快速得到高质量原型。
- 不让在线服务依赖 LLM。

做法：

1. 收集 200-500 条中文日记样例。
2. 覆盖显性和隐性情绪。
3. 用 LLM 离线辅助标注：
   - valence
   - arousal
   - primary label
   - top-k labels
   - evidence
4. 人工抽查和修正。
5. 用这些数据测试当前规则和未来小模型。

### 5.2 第二阶段：轻量文本 V-A 模型

推荐首选：

```text
BAAI/bge-small-zh-v1.5 + regression head
```

原因：

- 中文表现较好。
- 相对轻量。
- 适合部署在 CPU 或普通云容器。
- 可以输出 embedding，再接小型 MLP 回归 V-A。

中英混合备选：

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 + regression head
```

适合：

- 用户日记中中英文混写。
- 需要跨语言泛化。

更强但更重：

```text
hfl/chinese-macbert-base + regression head
```

适合：

- 更重视中文细腻语义。
- 服务器资源更充足。

不建议第一版使用：

```text
大型生成式 LLM 在线逐句分类
```

原因：

- 延迟高。
- 成本高。
- 网络不稳定会影响实时体验。
- 输出不够稳定，需要额外结构化约束。

### 5.3 第三阶段：模型蒸馏和量化

上线优化方向：

- ONNX Runtime
- int8 quantization
- batch segment inference
- debounce typing input
- 缓存相同 segment 的推理结果

目标：

```text
单次文本情绪推理 < 200ms
```

## 6. 渲染技术方案

### 6.1 渲染参数不只来自标签

建议映射关系：

```text
valence → 色相方向
arousal → 动画速度、字重、抖动幅度、缩放强度
confidence → 饱和度、透明度、边界清晰度
complexity → 渐变、多色冲突、分层阴影
dominance/control → 字距、排列秩序、压缩/扩张感
```

### 6.2 四象限基础渲染

#### 消极 + 高唤醒

代表：

- 愤怒
- 焦虑
- 紧张
- 烦躁

视觉：

- 红色系
- 高字重
- 字符紧缩
- 抖动或急促震动
- 边缘锐利

#### 积极 + 高唤醒

代表：

- 兴奋
- 开心
- 激动
- 期待

视觉：

- 黄色 / 橙色系
- 弹跳
- 字体扩张
- 节奏感
- 明亮高饱和

#### 消极 + 低唤醒

代表：

- 悲伤
- 低落
- 孤独
- 疲惫

视觉：

- 蓝色系
- 下坠
- 字重变轻
- 透明度降低
- 行距变疏

#### 积极 + 低唤醒

代表：

- 平静
- 放松
- 满足
- 安宁

视觉：

- 绿色 / 青绿色系
- 漂浮
- 缓慢呼吸
- 稳定排列
- 低冲突感

### 6.3 复杂情绪渲染

复杂情绪不是简单取平均。

例子：

```text
“我很开心能见到你，但其实也有点紧张。”
```

推荐渲染：

- “开心”部分使用积极高唤醒橙色。
- “紧张”部分使用消极高唤醒红色。
- 整体不强行平均成中性。
- 段落整体可以显示 “复杂情绪”。

视觉策略：

- segment-level 局部颜色。
- 多标签 top-k badge。
- 轻微双色渐变。
- 动画节奏不一致，表达内在冲突。

## 7. 分阶段优化路线

### Phase 0：稳定当前系统

目标：

- 确保页面不卡。
- LLM 失败时自动 fallback。
- `va_mapping` 始终可用。

任务：

- 保留 `va_mapper.py`。
- LLM 请求必须有 timeout。
- `/analyze-text` 即使没有 LLM，也必须返回 `va_mapping` 和本地 `llm_design`。

### Phase 1：增强规则识别

目标：

- 在不训练模型的前提下提升隐性情绪识别。

任务：

- 增加身体线索词典。
- 增加否认 / 弱化表达规则。
- 增加转折后加权规则。
- 增加关系线索和行为冲动规则。

输出：

```json
{
  "valence": -0.45,
  "arousal": 0.65,
  "confidence": 0.72,
  "evidence": ["身体紧绷", "否认式表达", "转折后加权"]
}
```

### Phase 2：建立标注数据集

目标：

- 为小模型训练和评估准备数据。

数据规模：

```text
MVP: 200-500 条
可用版: 1000-3000 条
较稳定版: 5000+ 条
```

每条数据建议标注：

- text
- segments
- valence
- arousal
- primary_label
- top_k_labels
- implicit_emotion
- evidence
- confidence

### Phase 3：训练轻量文本 V-A 模型

目标：

- 替代纯规则推理。
- 支持隐性语义识别。

推荐模型：

```text
BAAI/bge-small-zh-v1.5 + MLP regression head
```

输出：

```json
{
  "valence": -0.38,
  "arousal": 0.59,
  "confidence": 0.81,
  "embedding_confidence": 0.76
}
```

### Phase 4：升级标签推断

目标：

- 从“最近 V-A 点”升级为“语义 + V-A + evidence”的 top-k 标签系统。

任务：

- 新增 `emotion_labeler.py`。
- 输出 top-k labels。
- 对接前端标签候选和用户纠正。

### Phase 5：文本和语音融合

目标：

- 让语音输入不仅有文本语义，也有声学情绪。

任务：

- 新增 `emotion_fusion.py`。
- 融合 text V-A 和 audio VAD。
- 根据 ASR confidence、audio quality 动态调权。

### Phase 6：个性化校准

目标：

- 适配不同用户的表达方式。

任务：

- 保存用户手动修改过的标签。
- 学习用户个人词汇和情绪偏差。
- 做轻量个性化校准，不直接覆盖全局模型。

## 8. 推荐最终 API 结构

### `/analyze-text`

```json
{
  "status": "success",
  "input": {
    "text": "没事，我只是胸口有点紧。"
  },
  "text_emotion": {
    "segments": [
      {
        "text": "没事",
        "valence": -0.15,
        "arousal": 0.25,
        "confidence": 0.42,
        "evidence": ["否认式表达"]
      },
      {
        "text": "我只是胸口有点紧",
        "valence": -0.45,
        "arousal": 0.65,
        "confidence": 0.78,
        "evidence": ["身体紧绷", "弱化表达"]
      }
    ]
  },
  "va_mapping": {
    "segments": [],
    "overall": {}
  },
  "emotion_labels": {
    "primary": "焦虑",
    "top_k": [
      { "label": "焦虑", "score": 0.78 },
      { "label": "不安", "score": 0.71 },
      { "label": "压抑", "score": 0.54 }
    ],
    "is_complex": true
  },
  "llm_design": {}
}
```

### `/predict`

```json
{
  "status": "success",
  "asr": {},
  "text_emotion": {},
  "audio_emotion": {},
  "fusion": {},
  "va_mapping": {},
  "emotion_labels": {},
  "llm_design": {}
}
```

## 9. 关键设计原则

1. 不把 LLM 当作实时情绪分类器。
2. 不让 `va_mapper.py` 承担语义理解。
3. 不只用 V-A 最近点决定最终情绪标签。
4. 不把整段文本强行平均成单一情绪。
5. 保留 segment-level 情绪结果。
6. 让用户可以修改系统标签。
7. 把用户修改作为未来个性化校准数据。
8. 情绪反馈必须表达不确定性，避免诊断式措辞。
9. 渲染应该帮助用户觉察，而不是替用户下结论。

## 10. 下一步建议

最小可行优化顺序：

```text
1. 保留当前 va_mapper.py
2. 新增 text_emotion.py
3. 加入身体线索 / 否认 / 转折 / 关系线索规则
4. 返回 evidence 字段
5. 前端展示“为什么这样判断”
6. 收集用户修改标签
7. 建立小规模标注数据集
8. 训练 bge-small-zh-v1.5 + regression head
9. 新增 emotion_labeler.py
10. 做文本 + 语音 V-A fusion
```

