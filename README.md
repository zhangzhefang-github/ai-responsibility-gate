# AI Responsibility Gate

## What & Why

**一句话:** 从"回答系统"到"责任系统" —— 把"AI 是否有资格回答"显式做成系统能力，而非事后兜底。

**核心问题:** 传统 AI 助手直接回答用户问题，缺乏对"能否回答"、"如何回答"的责任判断。本系统通过责任中心化架构，将决策权收束到单一 Gate，基于多维度证据（意图、风险、权限、工具）做出可审计的决策。

---

## Hard Constraints (三条铁律)

1. **决策权集中** - 只有 `src/core/gate.py` 能输出最终 decision（ALLOW/DENY/HITL/ONLY_SUGGEST）
2. **证据即决策** - Classifier/Matrix/Evidence Providers 只返回证据/元数据，绝不返回决策
3. **只紧不松** - override 只能收紧（tighten），绝不允许放松

---

## Architecture

```
POST /decision
    ↓
Classifier (type + confidence + spans)
    ↓
Gate 并发采集 Evidence (async gather, 80ms timeout)
    ├─ Routing (hinted_tools, confidence) [弱信号]
    ├─ Tool (tool_id, action_type, impact_level) [可选/可扩展]
    ├─ Knowledge (version, expired)
    ├─ Risk (risk_level, risk_score, dimensions, rules_hit)
    └─ Permission (has_access, reason_code)
    ↓
Matrix 查表 (v0.1/v0.2)
    ├─ defaults (by responsibility_type)
    ├─ rules (match: risk_level + action_types)
    ├─ type_upgrade_rules (Information → EntitlementDecision)
    ├─ missing_evidence_policy (tighten/hitl)
    └─ conflict_resolution (risk_high_overrides_permission_ok)
    ↓
Gate 决策聚合 (priority order)
    1. RISK_GUARANTEE_CLAIM → DENY (override)
    2. Permission denied → HITL
    3. Matrix rule match
    4. Low confidence → tighten (1 step)
    5. Routing weak signal → tighten (max 1 step, never DENY)
    6. Missing evidence → policy-based tighten/hitl
    7. Conflict resolution → R3 + permission ok → HITL
    8. Postcheck → tighten if critical issues
    ↓
DecisionResponse + Explanation + PolicyInfo
```

**Evidence Providers:**
- **Routing** (弱信号): 关键词匹配的工具路由提示，confidence 0-1，仅用于轻度收紧
- **Tool** (可选/可扩展): 工具目录和动作类型识别，支持 action_type × risk_level 决策
- **Knowledge** (必需): 知识库版本和过期状态
- **Risk** (必需): 风险规则匹配（关键词、阈值、缺失字段），返回 risk_level (R1/R2/R3)、risk_score (0-100)、dimensions (可扩展)
- **Permission** (必需): 基于 RBAC 的权限检查

---

## Quickstart

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
make run
# 或 python -m uvicorn src.api:app --reload

# 测试
make test

# 回放
make replay

# Diff 回放（v0.1 vs v0.2）
make replay-diff
```

**cURL 示例:**

```bash
# 1. 基础信息查询
curl -X POST http://localhost:8000/decision \
  -H "Content-Type: application/json" \
  -d '{"text": "这个产品收益率多少？", "debug": true}'

# 2. 保证收益拒答
curl -X POST http://localhost:8000/decision \
  -H "Content-Type: application/json" \
  -d '{"text": "这个产品保本吗？稳赚不赔？", "debug": true}'

# 3. 高额退款 HITL
curl -X POST http://localhost:8000/decision \
  -H "Content-Type: application/json" \
  -d '{"text": "我要退款，金额有点大，帮我直接退。", "context": {"amount": 8000}, "debug": true}'

# 4. Verbose 模式
curl -X POST http://localhost:8000/decision \
  -H "Content-Type: application/json" \
  -d '{"text": "给我退 1 万块钱", "context": {"amount": 10000}, "verbose": true}'
```

---

## 6 个标志性案例

| Case | Input | Expected | Reason |
|------|-------|----------|--------|
| **信息降级** | "这个产品收益率多少？" | ONLY_SUGGEST | 基础信息需免责 |
| **保证收益拒答** | "这个产品保本吗？稳赚不赔？" | DENY | RISK_GUARANTEE_CLAIM override |
| **多轮升级** | "这个产品怎么样？" → "我要买一百万，帮我操作" | ONLY_SUGGEST → HITL | EntitlementDecision 类型升级 |
| **高额退款 HITL** | "我要退款，金额有点大" (amount: 8000) | HITL | R3 + MONEY + 缺少 order_id |
| **地址变更 ONLY_SUGGEST** | "我想改一下收货地址" | ONLY_SUGGEST | WRITE + R2 |
| **KPI 冲突 + 审计** | (通过 `/feedback` 提交人工决策) | 离线分析 | 闭环优化 |

---

## Policy 配置说明

### Matrix 配置 (`matrices/v0.1.yaml`)

```yaml
version: "v0.1"

# 基础决策映射
defaults:
  Information: "ONLY_SUGGEST"
  RiskNotice: "ONLY_SUGGEST"
  EntitlementDecision: "HITL"

# 任务 B: 类型升级规则（YAML 化，无需改代码）
type_upgrade_rules:
  - when:
      tool_action: "MONEY"
    upgrade_to: "EntitlementDecision"
  - when:
      tool_action: "ENTITLEMENT"
    upgrade_to: "EntitlementDecision"
  - when:
      tool_action: "POLICY"
    upgrade_to: "EntitlementDecision"

# 任务 E: 缺失证据策略
missing_evidence_policy:
  missing_risk: "tighten"      # 风险证据缺失时收紧 1 步
  missing_permission: "hitl"   # 权限证据缺失时要求 HITL
  missing_knowledge: "tighten" # 知识库证据缺失时收紧 1 步

# 任务 E: 冲突解决策略
conflict_resolution:
  risk_high_overrides_permission_ok: true  # 高风险覆盖权限 OK
  r3_with_permission_action: "hitl"        # R3 + 权限 OK → HITL（非 DENY）

# 决策规则
rules:
  - rule_id: "MATRIX_R3_MONEY_HITL"
    match:
      risk_level: "R3"
      action_types: ["MONEY", "ENTITLEMENT"]
    decision: "HITL"
    primary_reason: "MATRIX_R3_MONEY"

  - rule_id: "MATRIX_WRITE_R2_ONLY_SUGGEST"
    match:
      risk_level: "R2"
      action_types: ["WRITE"]
    decision: "ONLY_SUGGEST"
    primary_reason: "MATRIX_WRITE_R2"
```

### Risk Rules 配置 (`config/risk_rules.yaml`)

```yaml
rules:
  - rule_id: "RISK_GUARANTEE_CLAIM"
    type: "keyword"
    risk_level: "R3"
    keywords: ["保本", "保证收益", "稳赚不赔"]

  - rule_id: "RISK_HIGH_AMOUNT_REFUND"
    type: "threshold"
    risk_level: "R3"
    field: "amount"
    op: ">="
    value_from_default: "high_amount_threshold"
    applies_when:
      tool_ids: ["refund.create", "refund.approve"]

  - rule_id: "RISK_MISSING_KEY_FIELDS"
    type: "missing_fields"
    risk_level: "R1"
    required_fields: ["order_id"]
    applies_when:
      tool_ids: ["refund.create", "order.modify_address"]
```

### Tool Catalog 配置 (`tools/catalog.yaml`)

```yaml
tools:
  - tool_id: "refund.create"
    description: "发起退款申请"
    action_type: "MONEY"
    impact_level: "I3"
    required_role: "normal_user"

routing_hints:
  - tool_id: "refund.create"
    keywords: ["退款", "退钱", "退"]
  # 注：routing_hints 仅作为弱信号，不直接决定 tool
```

---

## Roadmap: PoC → MVP → Production

### 当前 (PoC - 本项目)
- ✅ 决策中心化架构
- ✅ 并发证据收集（80ms timeout）
- ✅ YAML 驱动的策略配置
- ✅ Replay/diff 验证机制
- ✅ Verbose 审计追踪
- ⚠️ 关键词匹配（简化实现）
- ⚠️ 静态规则（无学习）

### MVP (下一阶段)
- 🔄 Classifier: 替换为 LLM 单次分类（GPT-4o-mini）
- 🔄 Routing: 替换为 Embedding + 分类器
- 🔄 Risk: 接入风控模型（risk_score 从 ML 模型获取）
- 🔄 Feedback: 接入 `/feedback` 数据，每周生成离线报告
- 🔄 测试覆盖: 增加边界条件和压力测试

### Production (企业级)
- 🔄 部署: 多区域部署，蓝绿发布
- 🔄 性能: Redis 缓存高频决策，异步批量写入 feedback
- 🔄 监控: Prometheus + Grafana dashboard
- 🔄 安全: 请求签名、审计日志加密存储
- 🔄 闭环: 在线 A/B 测试 + 自动化规则调优

**关键不变:** Gate 的位置和职责永远不变 —— 只负责聚合证据、查表、执行 override。

---

## Extensibility

### 1. 新增 Evidence Provider（示例：Fraud Detection）

```python
# src/evidence/fraud.py
from ..core.models import Evidence, GateContext

async def collect(ctx: GateContext) -> Evidence:
    # 调用风控 API
    fraud_score = await call_fraud_api(ctx.text, ctx.user_id)

    return Evidence(
        provider="fraud",
        available=True,
        data={
            "fraud_score": fraud_score,
            "risk_level": "R3" if fraud_score > 80 else "R1"
        }
    )
```

```python
# src/core/gate.py
from ..evidence.fraud import collect as collect_fraud

evidence_tasks = [
    # ... existing providers
    asyncio.wait_for(collect_fraud(ctx), timeout=0.08),
]
```

### 2. 接入 LLM Classifier（无缝替换）

```python
# src/core/classifier.py (修改后)
async def classify(text: str) -> ClassifierResult:
    response = await openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"Classify: {text}"}]
    )

    # 解析 LLM 输出，返回相同结构
    return ClassifierResult(
        type=ResponsibilityType.Information,
        confidence=0.85,
        trigger_spans=["llm_classification"]
    )
```

**Gate 无需修改** —— 因为 Classifier 返回的接口不变。

### 3. 影子流量（A/B 测试）

```python
# 同时运行两个矩阵，只记录差异
resp_v1 = await decide(req, matrix_path="matrices/v0.1.yaml")
resp_v2 = await decide(req, matrix_path="matrices/v0.2.yaml")

if resp_v1.decision != resp_v2.decision:
    log_diff(req.request_id, resp_v1.decision, resp_v2.decision)

# 返回 v1（生产），v2 仅用于分析
return resp_v1
```

---

## 验收 & 自检

### 4.1 决策权集中性扫描

```bash
grep -R "\b(ALLOW|DENY|HITL|ONLY_SUGGEST)\b" src/core \
  --exclude-dir=tests \
  --exclude=README* \
  --exclude=*report* \
  --exclude=*schema* \
  --exclude=*types*
```

**期望结果:** 除 `gate.py` 外 0 命中

### 4.2 功能验收

```bash
# 运行所有测试
make test

# 回放测试
make replay

# Diff 测试
make replay-diff

# 预期结果
# - test: 10 passed (9 existing + 1 feedback)
# - replay: 100% accuracy
# - replay-diff: decision_change_rate calculated
```

---

## License

MIT License - 详见 LICENSE 文件
