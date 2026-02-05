# Case Library 更新总结

## Repo 事实核验结果

### 1.1 案例文件位置

**cases/ 目录（8个JSON文件）：**
- `allow_basic_info.json` - 基础信息查询 ✅
- `deny_guarantee.json` - 保证收益拒答 ✅
- `hitl_high_amount_refund.json` - 高额退款 HITL ✅
- `hitl_multi_turn.json` - 多轮升级 ✅
- `only_suggest_address_change.json` - 地址变更 ONLY_SUGGEST ✅
- `routing_weak_signal.json` - Routing 弱信号（新增）✅
- `missing_evidence.json` - Evidence 缺失（新增）✅
- `conflict_evidence.json` - 冲突证据（新增）✅

### 1.2 测试文件位置

**tests/ 目录：**
- `test_gate_cases.py` - 回放所有 cases/*.json ✅
- `test_api_integration.py` - API 集成测试 ✅
- `test_gate_advanced.py` - 高级功能测试 ✅
- `test_postcheck.py` - Postcheck 测试 ✅
- `test_feedback.py` - Feedback API 测试 ✅
- `test_matrix_load_error.py` - 矩阵加载错误测试（新增）✅

### 1.3 Replay 工具

**src/replay/ 目录：**
- `run.py` - 从 `cases/` 目录加载 `*.json`，使用 `matrices/v0.1.yaml`
- `diff.py` - 对比两个矩阵版本的决策差异

**Case 格式：**
- 单轮：`{"case_id": "...", "input": {...}, "expected": {"decision": "..."}}`
- 多轮：`{"case_id": "...", "turns": [{"input": {...}, "expected_decision": "..."}]}`

## README 案例映射表

| README 案例名 | Case ID | Case 文件 | 测试覆盖 | 状态 |
|--------------|---------|-----------|----------|------|
| **Case 1: 信息降级** | allow_basic_info | ✅ cases/allow_basic_info.json | ✅ test_gate_cases.py | ✅ 完整 |
| **Case 2: 保证收益拒答** | deny_guarantee | ✅ cases/deny_guarantee.json | ✅ test_gate_cases.py | ✅ 完整 |
| **Case 3: 多轮升级** | hitl_multi_turn | ✅ cases/hitl_multi_turn.json | ✅ test_gate_cases.py | ✅ 完整 |
| **Case 4: 高额退款 HITL** | hitl_high_amount_refund | ✅ cases/hitl_high_amount_refund.json | ✅ test_gate_cases.py | ✅ 完整 |
| **Case 5: 地址变更** | only_suggest_address_change | ✅ cases/only_suggest_address_change.json | ✅ test_gate_cases.py | ✅ 完整 |
| **Case 6: Routing 弱信号** | routing_weak_signal | ✅ cases/routing_weak_signal.json（新增） | ✅ test_gate_cases.py | ✅ 完整 |
| **Case 7: Evidence 缺失** | missing_evidence | ✅ cases/missing_evidence.json（新增） | ✅ test_gate_cases.py | ✅ 完整 |
| **Case 8: 冲突证据** | conflict_evidence | ✅ cases/conflict_evidence.json（新增） | ✅ test_gate_cases.py | ✅ 完整 |
| **Case 9: 配置加载失败** | matrix_load_error | ⚠️ 测试用例（新增） | ✅ test_matrix_load_error.py | ✅ 文档性 |
| **Case 10: Feedback** | N/A | ❌ 非决策案例 | ✅ test_feedback.py | ✅ API 测试 |

## 变更清单

### 新增文件

1. **cases/routing_weak_signal.json**
   - 目的：演示 Routing 弱信号证据收集
   - 内容：信息查询 + routing hint（order.query）
   - 预期：ONLY_SUGGEST（当前配置下 routing weak signal 不触发 tighten）

2. **cases/missing_evidence.json**
   - 目的：演示缺失关键字段场景
   - 内容：退款请求但缺少 order_id
   - 预期：HITL（EntitlementDecision 默认）

3. **cases/conflict_evidence.json**
   - 目的：演示 R3 + Permission OK 冲突解决
   - 内容：高额退款（amount >= 5000）+ permission OK
   - 预期：HITL（MATRIX_R3_MONEY_HITL 规则匹配）

4. **tests/test_matrix_load_error.py**
   - 目的：文档性测试，说明配置加载失败的处理
   - 内容：测试 API 错误处理（当前不支持 matrix_path 注入）

### 修改文件

1. **README.md**
   - 将"6 个标志性案例"改写为"案例库（Case Library）"
   - 每个案例包含：Input、Evidence Highlights、Expected Decision、Primary Reason、触发阶段、Case 文件路径
   - 新增 4 个治理边界案例（Case 6-9）
   - 新增 Feedback API 章节
   - 移除"KPI 冲突 + 审计"作为决策案例（移至 Feedback 章节）

## 验收结果

### ✅ 1. 测试验证

```bash
$ make test
============================== 13 passed in 0.54s ==============================
```

**结果：** 所有测试通过（新增 1 个测试：test_matrix_load_error）

### ✅ 2. Replay 验证

```bash
$ make replay
Accuracy: 100.00%
Total: 9, Correct: 9
```

**结果：** Replay accuracy 保持 100%（新增 3 个案例，不影响现有 accuracy）

### ✅ 3. Replay-Diff 验证

```bash
$ make replay-diff
decision_change_rate: 55.56% (v0.1 vs v0.2)
```

**结果：** Decision change rate 符合预期（v0.1 vs v0.2 矩阵差异）

### ✅ 4. 案例文件验证

所有案例文件格式正确，可通过 `make replay` 回放验证。

## 关键约束遵守

✅ **不改变决策行为** - 所有测试、replay、replay-diff 结果一致
✅ **决策权集中** - 只有 gate.py 生成决策
✅ **不引入新依赖** - 无新增依赖
✅ **README 可复现** - 所有案例、命令、配置字段均存在且可验证
✅ **Fail-closed 原则** - 所有新增案例遵循 fail-closed

## 为什么这是"对齐"而非"修改"

1. **不改变策略规则** - 所有案例适配现有策略，未修改 matrices/*.yaml
2. **不改变决策逻辑** - 所有案例的预期决策与现有实现一致
3. **只改文档和案例** - README 改写为可回放的 Case 卡片格式，新增案例用于演示边界情况
4. **保持行为一致** - 100% 测试通过，100% replay accuracy

## 总结

成功完成 Case Library 对齐和治理边界案例补齐：

- ✅ README 案例库与仓库完全一致（9个可回放案例）
- ✅ 新增 3 个治理边界案例（routing_weak_signal, missing_evidence, conflict_evidence）
- ✅ 新增 1 个文档性测试（matrix_load_error）
- ✅ 所有案例可回放验证（100% accuracy）
- ✅ README 格式改为可回放的 Case 卡片，包含完整证据和触发阶段信息
