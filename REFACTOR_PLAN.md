# Gate.py 重构计划

## 当前结构分析（451行）

### 主要组件：
1. **常量** (19-30行)
   - REASONS: 原因代码映射
   - STRICT_ORDER: 决策严格顺序 ["ALLOW", "ONLY_SUGGEST", "HITL", "DENY"]

2. **工具函数** (32-57行)
   - `tighten(decision, steps)` - 收紧决策
   - `_extract_evidence(result)` - 提取证据
   - `_build_summary(decision, reason, ...)` - 构建摘要

3. **Stage 1: 证据收集** (63-107行)
   - `_collect_all_evidence(ctx, trace)` - 并发收集所有证据
   - 返回: dict of Evidence

4. **Stage 2: 类型升级规则** (113-134行)
   - `_apply_type_upgrade_rules(matrix, classifier_result, action_type, trace)`
   - 返回: ResponsibilityType

5. **Stage 3: 矩阵查找** (140-187行)
   - `_lookup_matrix_decision(...)` 
   - 返回: (Decision, str, List[str], Optional[dict])
   - ⚠️ 问题：返回 Decision enum

6. **Stage 4: 缺失证据策略** (193-235行)
   - `_apply_missing_evidence_policy(decision, primary_reason, evidence, matrix, trace)`
   - 返回: (Decision, str)
   - ⚠️ 问题：返回 Decision enum

7. **Stage 5: 冲突解决和覆盖** (241-287行)
   - `_apply_conflict_resolution_and_overrides(decision, primary_reason, ...)`
   - 返回: (Decision, str)
   - ⚠️ 问题：返回 Decision enum

8. **主流程** (293-450行)
   - `decide(req, matrix_path)` - 编排所有阶段
   - 最终写入 DecisionResponse.decision

## 重构目标

### 新文件结构：

**gate_helpers.py** - 工具函数（不涉及 Decision）
- `tighten_one_step(current_index, steps)` - 返回新的索引
- `extract_evidence(result)` - 提取证据
- `build_summary(decision_value, reason, ...)` - 构建摘要（接受字符串）
- `get_decision_index(decision_value)` - 获取决策在严格顺序中的索引
- `format_trace_*()` - trace 格式化辅助函数

**gate_stages.py** - 阶段函数（返回中间状态，不返回 Decision enum）
- `collect_evidence(ctx, trace)` - 返回证据字典
- `apply_type_upgrade_rules(...)` - 返回 ResponsibilityType
- `lookup_matrix(...)` - 返回字典：{default_decision_str, primary_reason, rules_fired, matched_rule, ...}
- `apply_missing_evidence_policy(...)` - 返回字典：{tighten_steps, primary_reason}
- `apply_conflict_resolution_and_overrides(...)` - 返回字典：{tighten_steps, primary_reason, ...}

**gate.py** - 只保留 orchestration 和 Decision 映射
- `decide(req, matrix_path)` - 调用 stages，最后统一映射为 Decision enum
- 常量：REASONS, STRICT_ORDER（仅用于映射）
- Decision 写入点：只在最后一步写入 DecisionResponse.decision

## 关键约束

1. gate_stages.py 和 gate_helpers.py 不得包含字符串 "ALLOW", "DENY", "HITL", "ONLY_SUGGEST"
2. gate_stages.py 和 gate_helpers.py 不得导入 Decision enum
3. 所有阶段函数返回中间状态（字符串、字典、索引等），不返回 Decision
4. 只有 gate.py 在最后一步将中间状态映射为 Decision enum

## 中间状态设计

### lookup_matrix 返回：
```python
{
    "default_decision_str": "ONLY_SUGGEST",  # 字符串，不是 enum
    "primary_reason": "DEFAULT_DECISION",
    "rules_fired": ["MATRIX_R3_MONEY_HITL"],
    "matched_rule": {...},
    "has_guarantee_override": False,
    "has_permission_denied": False,
}
```

### apply_missing_evidence_policy 返回：
```python
{
    "tighten_steps": 1,  # 需要收紧的步数
    "primary_reason": "EVIDENCE_RISK_MISSING",
}
```

### apply_conflict_resolution_and_overrides 返回：
```python
{
    "tighten_steps": 1,
    "primary_reason": "CLASSIFIER_LOW_CONFIDENCE",
    "has_r3_conflict": False,
    "has_low_confidence": True,
    "has_routing_signal": False,
}
```

## 执行步骤

1. ✅ 分析当前结构
2. ⏳ 创建 gate_helpers.py
3. ⏳ 创建 gate_stages.py
4. ⏳ 重构 gate.py
5. ⏳ 验证无决策泄漏
6. ⏳ 运行测试验证行为一致
