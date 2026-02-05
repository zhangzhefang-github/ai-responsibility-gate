# Case Library 核验报告

## Step 1: Repo 事实核验结果

### 1.1 案例文件位置

**cases/ 目录（5个JSON文件）：**
- `allow_basic_info.json` - 基础信息查询
- `deny_guarantee.json` - 保证收益拒答
- `hitl_high_amount_refund.json` - 高额退款 HITL
- `hitl_multi_turn.json` - 多轮升级
- `only_suggest_address_change.json` - 地址变更 ONLY_SUGGEST

### 1.2 测试文件位置

**tests/ 目录：**
- `test_gate_cases.py` - 回放所有 cases/*.json
- `test_api_integration.py` - API 集成测试
- `test_gate_advanced.py` - 高级功能测试（low_confidence, debug_flag, replay_diff）
- `test_postcheck.py` - Postcheck 测试
- `test_feedback.py` - Feedback API 测试

### 1.3 Replay 工具

**src/replay/ 目录：**
- `run.py` - 从 `cases/` 目录加载 `*.json`，使用 `matrices/v0.1.yaml`
- `diff.py` - 对比两个矩阵版本的决策差异

**Case 格式：**
```json
{
  "case_id": "xxx",
  "input": {"text": "...", "context": {...}},
  "expected": {"decision": "ONLY_SUGGEST"}
}
// 或
{
  "case_id": "xxx",
  "turns": [
    {"input": {...}, "expected_decision": "..."}
  ]
}
```

### 1.4 README 案例映射表

| README 案例名 | Case ID | Case 文件 | 测试覆盖 | 状态 |
|--------------|---------|-----------|----------|------|
| **信息降级** | allow_basic_info | ✅ cases/allow_basic_info.json | ✅ test_gate_cases.py | ✅ 完整 |
| **保证收益拒答** | deny_guarantee | ✅ cases/deny_guarantee.json | ✅ test_gate_cases.py | ✅ 完整 |
| **多轮升级** | hitl_multi_turn | ✅ cases/hitl_multi_turn.json | ✅ test_gate_cases.py | ✅ 完整 |
| **高额退款 HITL** | hitl_high_amount_refund | ✅ cases/hitl_high_amount_refund.json | ✅ test_gate_cases.py | ✅ 完整 |
| **地址变更 ONLY_SUGGEST** | only_suggest_address_change | ✅ cases/only_suggest_address_change.json | ✅ test_gate_cases.py | ✅ 完整 |
| **KPI 冲突 + 审计** | N/A | ❌ 无 case 文件 | ✅ test_feedback.py | ⚠️ 非决策案例（feedback API） |

### 1.5 缺失的治理边界案例

根据要求，需要补齐以下4个治理边界案例：

1. **Case7: Routing 弱信号误触发** - ❌ MISSING
2. **Case8: Evidence 缺失/timeout** - ❌ MISSING  
3. **Case9: 冲突证据（Risk 高但 Permission OK）** - ❌ MISSING
4. **Case10: 配置/矩阵加载失败** - ⚠️ 部分覆盖（test_api_integration 可能有，需确认）

### 1.6 配置与证据细节

**风险规则（config/risk_rules.yaml）：**
- RISK_GUARANTEE_CLAIM: R3, keywords=["保本","保证收益","稳赚不赔"...]
- RISK_HIGH_AMOUNT_REFUND: R3, threshold >= 5000, applies_when tool_ids=["refund.create"]
- RISK_MISSING_KEY_FIELDS: R1, required_fields=["order_id"]

**矩阵规则（matrices/v0.1.yaml）：**
- defaults: Information→ONLY_SUGGEST, EntitlementDecision→HITL
- MATRIX_R3_MONEY_HITL: R3 + MONEY/ENTITLEMENT → HITL
- MATRIX_WRITE_R2_ONLY_SUGGEST: R2 + WRITE → ONLY_SUGGEST
- missing_evidence_policy: missing_risk→tighten, missing_permission→hitl
- conflict_resolution: R3 + permission ok → HITL

**Routing 弱信号：**
- 触发条件：decision_index == 0 (ALLOW) && routing_conf >= 0.7 && hinted_tools
- 效果：tighten 1 step，never DENY

## Step 2: 对齐 README 计划

需要将 README 的"6 个标志性案例"改写为：
1. 可回放的 Case 卡片格式
2. 包含 Input、Evidence highlights、Expected decision、reason_code、触发阶段
3. 移除"KPI 冲突 + 审计"（非决策案例，移到 Feedback 章节）
4. 新增4个治理边界案例

## Step 3: 补齐治理边界案例计划

1. **Case7: Routing 弱信号误触发**
   - Input: "我想退订邮件通知"（含"退"但非退款）
   - Expected: 不应走 MONEY 链路，routing 最多 tighten 1 步
   - Case 文件: `cases/routing_weak_signal.json`

2. **Case8: Evidence 缺失**
   - 模拟：context 中缺少 order_id，触发 RISK_MISSING_KEY_FIELDS
   - Expected: 按 missing_evidence_policy tighten
   - Case 文件: `cases/missing_evidence.json`

3. **Case9: 冲突证据（R3 + Permission OK）**
   - Input: 高额退款（amount >= 5000）+ permission ok
   - Expected: conflict_resolution → HITL（非 DENY）
   - Case 文件: `cases/conflict_evidence.json`

4. **Case10: 配置加载失败**
   - 测试：指向不存在的 matrix path
   - Expected: HTTP 500，不产生假决策
   - 测试文件: `tests/test_matrix_load_error.py`
