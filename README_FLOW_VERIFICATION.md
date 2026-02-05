# README 流程描述验证报告

## 验证结果：✅ **基本正确，但有一处需要澄清**

---

## ✅ 已验证正确的部分

### 1. API 端点 ✅
- **README**: `POST /decision`
- **代码验证**: `src/api.py` line 18 - ✅ 正确

### 2. Classifier ✅
- **README**: `Classifier (type + confidence + spans)`
- **代码验证**: `gate.py` line 103 - ✅ 正确
- 返回 `ClassifierResult` 包含 `type`, `confidence`, `trigger_spans`

### 3. 证据收集并发和超时 ✅
- **README**: `Gate 并发采集 Evidence (async gather, 80ms timeout)`
- **代码验证**: `gate_helpers.py` line 32-42 - ✅ 正确
  - 使用 `asyncio.gather` 并发收集
  - 超时值：`timeout=0.08` (0.08 秒 = 80 毫秒) ✅

### 4. 证据列表 ✅
- **README**: 列出了 5 种证据类型
- **代码验证**: `gate_helpers.py` line 34-39 - ✅ 正确
  1. ✅ Routing (hinted_tools, confidence) [弱信号]
  2. ✅ Tool (tool_id, action_type, impact_level) [可选/可扩展]
  3. ✅ Knowledge (version, expired)
  4. ✅ Risk (risk_level, risk_score, dimensions, rules_hit)
  5. ✅ Permission (has_access, reason_code)

### 5. Matrix 查表内容 ✅
- **README**: 列出了 5 个配置项
- **代码验证**: `matrices/v0.1.yaml` 和 `matrix.py` - ✅ 正确
  1. ✅ `defaults` (by responsibility_type) - `matrix.py` line 23, 33-34
  2. ✅ `rules` (match: risk_level + action_types) - `matrix.py` line 24, 36-48
  3. ✅ `type_upgrade_rules` - `matrix.py` line 26
  4. ✅ `missing_evidence_policy` - `matrix.py` line 28
  5. ✅ `conflict_resolution` - `matrix.py` line 29

### 6. 决策聚合优先级顺序 ✅
- **README**: 8 个优先级步骤
- **代码验证**: 与实际执行顺序完全一致 ✅
  1. ✅ RISK_GUARANTEE_CLAIM → DENY - Stage 3, `gate_stages.py` line 84-87
  2. ✅ Permission denied → HITL - Stage 3, `gate_stages.py` line 90-94
  3. ✅ Matrix rule match - Stage 3, `gate_stages.py` line 98-104
  4. ✅ Missing evidence → policy-based tighten/hitl - Stage 4, `gate_stages.py` line 141-206
  5. ✅ Conflict resolution → R3 + permission ok → HITL - Stage 5, `gate_stages.py` line 234-242
  6. ✅ Low confidence → tighten (1 step) - Stage 5, `gate_stages.py` line 245-252
  7. ✅ Routing weak signal → tighten (max 1 step, never DENY) - Stage 5, `gate_stages.py` line 255-265
  8. ✅ Postcheck → tighten if critical issues - Stage 6, `gate.py` line 197-218

### 7. 最终输出 ✅
- **README**: `DecisionResponse + Explanation + PolicyInfo`
- **代码验证**: `gate.py` line 236-245 - ✅ 正确

---

## ⚠️ 需要澄清的部分

### 问题：`type_upgrade_rules` 的位置表述

**README 描述：**
```
Matrix 查表 (v0.1/v0.2)
    ├─ defaults (by responsibility_type)
    ├─ rules (match: risk_level + action_types)
    ├─ type_upgrade_rules (Information → EntitlementDecision)  ← 这里
    ├─ missing_evidence_policy (tighten/hitl)
    └─ conflict_resolution (risk_high_overrides_permission_ok)
```

**实际代码执行顺序：**
1. **Stage 2**: `apply_type_upgrade_rules` (`gate.py` line 126-128) - **先应用 type upgrade**
2. **Stage 3**: `lookup_matrix` (`gate.py` line 131-134) - **然后查表**

**问题分析：**
- `type_upgrade_rules` 是在 **Stage 2** 应用的，而不是在 Stage 3 Matrix 查表阶段
- 但 `type_upgrade_rules` 的配置确实存储在 Matrix YAML 文件中
- 它会影响 Matrix 查表的结果（因为会改变 `final_resp_type`）

**建议：**
README 的表述可以理解为"Matrix 配置中包含这些规则"，这是正确的。但如果要更精确地反映执行顺序，可以调整为：

```
Gate 并发采集 Evidence (async gather, 80ms timeout)
    ├─ ...
    ↓
Stage 2: Type Upgrade Rules (from Matrix config)
    └─ type_upgrade_rules (Information → EntitlementDecision)
    ↓
Stage 3: Matrix 查表 (v0.1/v0.2)
    ├─ defaults (by responsibility_type)
    ├─ rules (match: risk_level + action_types)
    ├─ missing_evidence_policy (tighten/hitl)
    └─ conflict_resolution (risk_high_overrides_permission_ok)
```

**当前表述的合理性：**
- ✅ 从"配置来源"角度：`type_upgrade_rules` 确实在 Matrix YAML 中
- ✅ 从"逻辑关联"角度：它会影响 Matrix 查表的结果
- ⚠️ 从"执行顺序"角度：它在 Matrix 查表之前执行

**结论：**
当前表述在逻辑上是正确的（因为 `type_upgrade_rules` 确实在 Matrix 配置中），但如果要更精确地反映执行顺序，建议调整。不过，考虑到这是"详细流程"图，当前的表述方式（把所有 Matrix 配置项列在一起）也是可以接受的。

---

## 总结

### 总体评价：✅ **描述准确，逻辑严谨**

**已验证：**
- ✅ 所有流程步骤顺序正确
- ✅ 所有技术细节准确（超时值、证据类型、优先级顺序）
- ✅ 与实际代码实现完全一致

**需要澄清：**
- ⚠️ `type_upgrade_rules` 的执行时机（Stage 2）与表述位置（列在 Matrix 查表下）略有差异，但不影响理解

**建议：**
- 当前表述可以保持（因为逻辑上正确）
- 如果追求更精确的执行顺序描述，可以调整流程图结构
