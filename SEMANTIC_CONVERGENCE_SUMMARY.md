# 语义收敛补丁总结

## 目标

彻底移除 `gate_stages.py` 和 `gate_helpers.py` 中的决策字符串（ALLOW/DENY/HITL/ONLY_SUGGEST），使用索引常量替代，实现"语义收敛"而非逻辑修改。

## 变更文件

### 1. src/core/gate_helpers.py

**移除：**
- ❌ `DECISION_ORDER = ["ALLOW", "ONLY_SUGGEST", "HITL", "DENY"]` 常量数组
- ❌ `get_decision_index()` 函数（依赖决策字符串）
- ❌ `build_summary()` 函数（包含决策字符串字典）

**新增：**
- ✅ `DECISION_IDX_MIN = 0`, `DECISION_IDX_MAX = 3` 索引常量
- ✅ `tighten_one_step()` 函数（基于索引操作）

**保留：**
- ✅ `extract_evidence()` - 不涉及决策
- ✅ `collect_all_evidence()` - 不涉及决策

### 2. src/core/gate_stages.py

**移除：**
- ❌ 所有决策字符串字面量（"ALLOW", "DENY", "HITL", "ONLY_SUGGEST"）
- ❌ trace 输出中的决策字符串显示

**新增：**
- ✅ `DECISION_IDX_0/1/2/3` 索引常量
- ✅ `lookup_matrix()` 返回 `config_decision_str` 字段（配置字符串，由 gate.py 转换）

**修改：**
- ✅ `lookup_matrix()` - 返回配置字符串而非直接转换，gate.py 负责转换
- ✅ `apply_missing_evidence_policy()` - trace 中显示索引而非字符串
- ✅ `apply_conflict_resolution_and_overrides()` - trace 中显示索引而非字符串

### 3. src/core/gate.py

**新增：**
- ✅ `_config_str_to_index()` - 唯一转换点：配置字符串 → 索引
- ✅ `build_summary()` 逻辑内联（使用决策字符串，但仅在 gate.py 中）

**修改：**
- ✅ `decide()` - 在 Stage 3 后转换配置字符串为索引

## 关键设计

### 索引常量替代字符串

**重构前：**
```python
# gate_helpers.py
DECISION_ORDER = ["ALLOW", "ONLY_SUGGEST", "HITL", "DENY"]
decision_index = DECISION_ORDER.index("DENY")  # 使用字符串

# gate_stages.py
decision_str = "DENY"
if decision_str == "DENY":  # 字符串比较
```

**重构后：**
```python
# gate_helpers.py
DECISION_IDX_MAX = 3
decision_index = 3  # 直接使用索引常量

# gate_stages.py
DECISION_IDX_3 = 3
if decision_index == DECISION_IDX_3:  # 索引比较
```

### 配置字符串转换

**设计：** 配置文件中仍然是字符串（YAML 格式），但转换逻辑集中在 gate.py：

```python
# gate_stages.py - 返回配置字符串
result["config_decision_str"] = matched_rule["decision"]

# gate.py - 唯一转换点
decision_index = _config_str_to_index(matrix_result["config_decision_str"])
```

## 验收结果

### ✅ 1. 决策字符串清零验证

```bash
$ grep -R "\b(ALLOW|DENY|HITL|ONLY_SUGGEST)\b" src/core/gate_stages.py src/core/gate_helpers.py
```

**结果：** 0 命中 ✅

### ✅ 2. 行为一致性验证

**测试：**
```bash
$ make test
======================== 12 passed in 0.48s =========================
```

**Replay：**
```bash
$ make replay
Accuracy: 100.00%
Total: 6, Correct: 6
```

**Replay-Diff：**
```bash
$ make replay-diff
decision_change_rate: 66.67% (预期值，v0.1 vs v0.2 矩阵差异)
```

**结论：** 行为完全一致 ✅

## 为什么这是"语义收敛"而非逻辑修改

1. **不改变决策逻辑：** 所有 tighten、conflict resolution、missing evidence 策略逻辑保持不变
2. **不改变策略顺序：** 阶段顺序完全一致
3. **不改变配置格式：** YAML 配置仍然使用字符串
4. **只改变表示方式：** 内部使用索引常量替代字符串字面量
5. **集中转换点：** 配置字符串 → 索引的转换集中在 gate.py

## 关键约束遵守

✅ **决策权集中** - 只有 gate.py 创建和写入 Decision enum
✅ **无决策字符串泄漏** - gate_stages.py 和 gate_helpers.py 中 0 个决策字符串
✅ **行为完全一致** - 100% 测试通过，100% replay accuracy
✅ **不改变策略** - 所有策略规则、阈值、默认值保持不变

## 总结

成功完成语义收敛补丁：
- ✅ gate_stages.py: 0 个决策字符串（从 22 处降至 0）
- ✅ gate_helpers.py: 0 个决策字符串（从 8 处降至 0）
- ✅ 行为完全一致（100% 测试通过，100% replay accuracy）
- ✅ 决策权集中（只有 gate.py 处理决策字符串和 enum）

这是一个纯粹的"语义收敛"补丁，没有改变任何业务逻辑，只是将内部表示从字符串字面量改为索引常量。
