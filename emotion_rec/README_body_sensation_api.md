# Body Sensation Advice API

身体感受功能当前页面入口：

- `/body`
- `/body-sensation`
- `/body_sensation`

前端文件：

- `emotion_rec/static/body_sensation.html`
- `emotion_rec/static/body_sensation.js`
- `emotion_rec/static/body_sensation.css`

## Endpoint

POST /body-sensation/advice

用于“身体感受”扩展功能。前端负责人体图、部位高亮、症状选择和补充输入；后端负责情绪分析、身体感受解释、低风险缓解建议和事件记录。

该接口不是医疗诊断接口。返回内容只用于情绪支持、身体信号整理和低风险自我照护提示；出现胸痛、呼吸困难、晕厥、剧烈头痛、麻木无力、血便或高烧等红旗信号时，应优先寻求专业医疗帮助。

## Request Example

{
  "participant_code": "P1234",
  "journal_text": "今天赶 deadline，一直很紧张，下午开始头疼，胃也有点抽。",
  "selected_regions": [
    {"id": "head", "label": "头部"},
    {"id": "stomach", "label": "胃部"}
  ],
  "symptoms": [
    {
      "region_id": "head",
      "label": "头疼",
      "severity": 3,
      "duration": "2小时"
    }
  ],
  "free_text": "今天喝了两杯咖啡，午饭吃得很晚。",
  "include_recent_diaries": true,
  "recent_diary_limit": 3
}

## Response Fields

- status
- body_sensation
- emotion_context
- possible_links
- advice
- safety
- recent_diaries_used
- logged

## Frontend Notes

前端只需要传 selected_regions、symptoms、free_text、journal_text 和 participant_code。

前端优先展示：

1. advice.title
2. advice.summary
3. advice.steps
4. advice.reflection_prompt
5. safety.red_flags

如果 safety.risk_level 是 high，前端必须明显提示用户及时寻求专业帮助。

Body 生成的低风险建议会记录到 `usage_events`，Review 和 Records 会把这类身体感受记录纳入统计和历史列表。

## Common Region IDs

- head
- eyes
- throat
- chest
- shoulder_neck
- stomach
- abdomen
- back
- hands
- legs
- whole_body

## Common Symptom Labels

- 头疼
- 头晕
- 胸闷
- 心跳过快
- 呼吸困难
- 胃痉挛
- 拉肚子
- 恶心
- 肌肉紧绷
- 疲惫
- 麻木

## LLM

生成式模型调用统一走 `emotion_rec/llm_client.py`，通过 OpenAI SDK 调用 DeepSeek。
`/analyze-text`、Body 建议、Diary 复盘和 Emotion Review 阶段复盘都应该复用同一个封装。失败或没有 key 时回退本地分类器/规则或本地建议 fallback。

身体感受接口默认启用 DeepSeek，高风险红旗仍会跳过 LLM 并走安全 fallback：

```text
DEEPSEEK_API_KEY=...
DEEPSEEK_MODEL=deepseek-v4-flash
BODY_ADVICE_LLM_ENABLED=1
BODY_LLM_MODEL=
BODY_LLM_TEMPERATURE=0.15
BODY_LLM_MAX_TOKENS=4096
```

设 `BODY_ADVICE_LLM_ENABLED=0` 可强制身体感受建议走本地 fallback。

不要在文档或代码中写入真实 `DEEPSEEK_API_KEY`、`OPENAI_API_KEY` 或其他平台 secret key。
