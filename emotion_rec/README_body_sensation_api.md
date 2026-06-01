# Body Sensation Advice API

## Endpoint

POST /body-sensation/advice

用于“身体感受”扩展功能。前端负责人体图、部位高亮、症状选择和补充输入；后端负责情绪分析、身体感受解释、低风险缓解建议和事件记录。

该接口不是医疗诊断接口。

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

实时 /analyze-text 不建议调用本地大模型。

身体感受接口可以单独启用本地 Qwen：

BODY_ADVICE_LLM_ENABLED=1
BODY_LLM_API_SCHEME=http
BODY_LLM_API_HOST=127.0.0.1
BODY_LLM_API_PORT=11434
BODY_LLM_MODEL=qwen3:4b
