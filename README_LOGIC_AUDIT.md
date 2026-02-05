# README 逻辑严谨性审核报告

## 审核范围

对照代码实现（`src/core/gate.py`, `src/core/gate_stages.py`, `src/api.py`, `src/core/models.py`）审核 README 中的技术描述、架构说明、案例和 API 文档的准确性。

---

## ✅ 正确的描述

### 1. 决策流程顺序 ✅

**README 描述：**
```
POST /decision
    ↓
Classifier (type + confidence + spans)
    ↓
Gate 并发采集 Evidence (async gather, 80ms timeout)
    ↓
Matrix 查表 (v0.1/v0.2)
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
```

**代码验证：**
- ✅ `gate.py` 中确实按此顺序执行
- ✅ Stage 1: Evidence Collection (line 109)
- ✅ Stage 2: Type Upgrade (line 126)
- ✅ Stage 3: Matrix Lookup (line 131)
- ✅ Stage 4: Missing Evidence Policy (line 146)
- ✅ Stage 5: Conflict Resolution & Overrides (line 153)
- ✅ Stage 6: Postcheck (line 197)

**结论：** ✅ 正确

### 2. 决策权集中 ✅

**README 描述：**
- "只有 `src/core/gate.py` 能输出最终 decision"

**代码验证：**
- ✅ `gate.py` line 161: `decision = _map_index_to_decision(decision_index)` - 唯一创建 Decision enum 的地方
- ✅ `gate.py` line 240: `decision=decision` - 唯一写入 DecisionResponse 的地方
- ✅ `gate_stages.py` 和 `gate_helpers.py` 只返回 index，不返回 Decision enum

**结论：** ✅ 正确

### 3. API 文档字段 ✅

**README 中的请求体：**
```json
{
  "text": "这个产品收益率多少？",
  "session_id": "可选",
  "user_id": "可选",
  "context": {...},
  "debug": false,
  "verbose": false
}
```

**代码验证：**
- ✅ `models.py` line 16-22: `DecisionRequest` 字段完全匹配
- ✅ `text`: required, min_length=1, max_length=10000 ✅
- ✅ `session_id`, `user_id`: Optional ✅
- ✅ `context`: Optional[Dict[str, Any]] ✅
- ✅ `debug`, `verbose`: bool, default=False ✅

**结论：** ✅ 正确

### 4. 响应字段 ✅

**README 中的响应体：**
```json
{
  "request_id": "uuid",
  "session_id": "可选",
  "responsibility_type": "Information",
  "decision": "ONLY_SUGGEST",
  "primary_reason": "DEFAULT_DECISION",
  "suggested_action": "handoff",
  "explanation": {...},
  "policy": {...},
  "latency_ms": 45
}
```

**代码验证：**
- ✅ `models.py` line 60-69: `DecisionResponse` 字段完全匹配
- ✅ 所有字段类型和结构一致 ✅

**结论：** ✅ 正确

### 5. Matrix 配置格式 ✅

**README 中的配置示例：**
```yaml
defaults:
  Information: "ONLY_SUGGEST"
  RiskNotice: "ONLY_SUGGEST"
  EntitlementDecision: "HITL"
```

**代码验证：**
- ✅ `matrices/v0.1.yaml` 格式完全一致 ✅

**结论：** ✅ 正确

---

## ⚠️ 需要修正的问题

### 问题 1: 决策聚合优先级顺序描述不准确 ⚠️

**README 描述：**
```
Gate 决策聚合 (priority order)
    1. RISK_GUARANTEE_CLAIM → DENY (override)
    2. Permission denied → HITL
    3. Matrix rule match
    4. Low confidence → tighten (1 step)
    5. Routing weak signal → tighten (max 1 step, never DENY)
    6. Missing evidence → policy-based tighten/hitl
    7. Conflict resolution → R3 + permission ok → HITL
    8. Postcheck → tighten if critical issues
```

**实际代码执行顺序：**
1. ✅ RISK_GUARANTEE_CLAIM → DENY (Stage 3, `gate_stages.py` line 84-87)
2. ✅ Permission denied → HITL (Stage 3, `gate_stages.py` line 90-94)
3. ✅ Matrix rule match (Stage 3, `gate_stages.py` line 98-104)
4. ✅ Missing evidence → policy-based tighten/hitl (Stage 4, `gate_stages.py` line 141-206)
5. ✅ Conflict resolution → R3 + permission ok → HITL (Stage 5, `gate_stages.py` line 234-242)
6. ✅ Low confidence → tighten (Stage 5, `gate_stages.py` line 245-252)
7. ✅ Routing weak signal → tighten (Stage 5, `gate_stages.py` line 255-265)
8. ✅ Postcheck → tighten (Stage 6, `gate.py` line 197-218)

**问题：**
- README 中 "Low confidence" 和 "Routing weak signal" 在 "Missing evidence" 之前，但实际代码中它们在 Stage 5（Conflict Resolution）中，在 Stage 4（Missing Evidence）之后。

**修正建议：**
调整顺序为：
```
Gate 决策聚合 (priority order)
    1. RISK_GUARANTEE_CLAIM → DENY (override)
    2. Permission denied → HITL
    3. Matrix rule match
    4. Missing evidence → policy-based tighten/hitl
    5. Conflict resolution → R3 + permission ok → HITL
    6. Low confidence → tighten (1 step)
    7. Routing weak signal → tighten (max 1 step, never DENY)
    8. Postcheck → tighten if critical issues
```

### 问题 2: Case 2 触发阶段描述不完整 ⚠️

**README 描述：**
```
#### Case 2: 保证收益拒答（deny_guarantee）
- **触发阶段**：Stage 3 (Matrix Lookup) - RISK_GUARANTEE_CLAIM override → DENY
```

**实际代码验证：**
- Stage 3: `gate_stages.py` line 84-87 确实会设置 `decision_index = DECISION_IDX_3` (DENY)
- 但 Stage 6 (Postcheck) 也会检测 guarantee keyword (`postcheck.py` line 14-20)
- 如果 Stage 3 已经设置为 DENY，Postcheck 不会再收紧（因为已经是最大值）

**问题：**
- 描述不完整，应该说明 Postcheck 也会检测，但由于已经是 DENY，不会进一步收紧。

**修正建议：**
```
- **触发阶段**：Stage 3 (Matrix Lookup) - RISK_GUARANTEE_CLAIM override → DENY, Stage 6 (Postcheck) - guarantee keyword detected (already DENY, no further tightening)
```

### 问题 3: API 文档中 "查询参数" 描述不准确 ⚠️

**README 描述：**
```
**查询参数:**
- `debug` (boolean, 默认: false) - 在响应中包含 `rules_fired`
- `verbose` (boolean, 默认: false) - 在标准输出打印详细追踪信息
```

**实际代码验证：**
- `debug` 和 `verbose` 是**请求体字段**，不是查询参数（query parameters）
- `api.py` line 18: `async def decision(req: DecisionRequest)` - 通过请求体接收

**问题：**
- 术语不准确，"查询参数"通常指 URL query string（如 `?debug=true`），但这里是请求体字段。

**修正建议：**
```
**请求参数:**
- `debug` (boolean, 默认: false) - 在响应中包含 `rules_fired`
- `verbose` (boolean, 默认: false) - 在标准输出打印详细追踪信息
```

### 问题 4: 应用场景配置示例可能不完整 ⚠️

**README 中的配置示例：**
```yaml
rules:
  - rule_id: "FINANCE_INVESTMENT_ADVICE"
    match:
      keywords: ["投资", "买入", "卖出", "推荐股票"]
      risk_level: "R3"
    decision: "DENY"
    primary_reason: "COMPLIANCE_INVESTMENT_ADVICE_PROHIBITED"
```

**实际代码验证：**
- `matrices/v0.1.yaml` 中的 rules 格式是：
  ```yaml
  rules:
    - rule_id: "MATRIX_R3_MONEY_HITL"
      match:
        risk_level: "R3"
        action_types: ["MONEY", "ENTITLEMENT"]
      decision: "HITL"
      primary_reason: "MATRIX_R3_MONEY"
  ```

**问题：**
- README 中的配置示例使用了 `keywords` 字段，但实际 Matrix rules 不支持 `keywords` 匹配
- `keywords` 匹配是在 Risk Rules (`config/risk_rules.yaml`) 中实现的，不是 Matrix rules

**修正建议：**
应该说明这是**概念性示例**，实际实现需要：
1. 在 `config/risk_rules.yaml` 中定义关键词规则
2. 在 `matrices/*.yaml` 中定义基于 risk_level 的决策规则

或者改为更准确的示例：
```yaml
# 步骤 1: config/risk_rules.yaml
rules:
  - rule_id: "RISK_INVESTMENT_ADVICE"
    type: "keyword"
    risk_level: "R3"
    keywords: ["投资", "买入", "卖出", "推荐股票"]

# 步骤 2: matrices/finance_compliance.yaml
rules:
  - rule_id: "MATRIX_R3_INVESTMENT_DENY"
    match:
      risk_level: "R3"
      action_types: ["MONEY"]  # 投资建议通常涉及 MONEY
    decision: "DENY"
    primary_reason: "COMPLIANCE_INVESTMENT_ADVICE_PROHIBITED"
```

---

## ✅ 其他验证

### 1. 硬约束描述 ✅
- ✅ "决策权集中" - 已验证，只有 `gate.py` 创建 Decision
- ✅ "证据即决策" - 已验证，Evidence Providers 只返回证据
- ✅ "只紧不松" - 已验证，`tighten_one_step` 只增加 index，不减少

### 2. 架构图 ✅
- ✅ Mermaid 图与实际流程一致
- ✅ 证据收集顺序正确
- ✅ 决策输出路径正确

### 3. 案例描述 ✅
- ✅ Case 1-5 的预期决策与实际代码逻辑一致
- ✅ 触发阶段描述基本准确（除 Case 2 需要补充）

### 4. 配置说明 ✅
- ✅ Matrix 配置格式正确
- ✅ Risk Rules 配置格式正确
- ✅ Tool Catalog 配置格式正确

---

## 总结

### 总体评价：**逻辑严谨性良好，但有 4 处需要修正**

**需要修正的问题：**
1. ⚠️ **决策聚合优先级顺序** - 需要调整顺序以匹配实际代码执行
2. ⚠️ **Case 2 触发阶段描述** - 需要补充 Postcheck 说明
3. ⚠️ **API 文档术语** - "查询参数" 应改为 "请求参数"
4. ⚠️ **应用场景配置示例** - 需要说明这是概念性示例，或提供更准确的实现步骤

**建议优先级：**
- **P0（必须修正）**：问题 1（决策聚合顺序）- 影响对系统行为的理解
- **P1（建议修正）**：问题 2、3、4 - 提高文档准确性
