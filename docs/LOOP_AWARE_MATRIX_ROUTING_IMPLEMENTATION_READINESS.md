# Implementation Readiness Notes: Loop-Aware Matrix Routing (Phase 1)

> 在进入代码实现前，明确设计约定与职责边界。本文档为 Phase 1 实施的前置规范。

---

## 1. loop_state 解析失败时的正式行为约定

### 1.1 设计说明

**约定**：当 `loop_state` 解析失败时，**fallback 到 base matrix，且不抛异常**。

### 1.2 具体行为

| 场景 | 行为 |
|------|------|
| `req.context` 无 `loop_state` | 不触发 loop 解析，使用 base matrix |
| `loop_state` 为 `None` / 空 dict | 不触发 loop 解析，使用 base matrix |
| `loop_state` 缺少 `round_index` 或 `nit_only_streak` | 视为解析失败，fallback 到 base matrix，不抛异常 |
| `loop_state` 类型错误（如 `round_index` 非 int） | 视为解析失败，fallback 到 base matrix，不抛异常 |
| `loop_state` 值越界（如 `round_index < 0`） | 视为解析失败，fallback 到 base matrix，不抛异常 |

### 1.3 实现方式

- 复用 `parse_loop_state()`（`src/core/loop_guard.py`）。该函数在解析失败时返回 `None`，不抛异常。
- `resolve_effective_matrix_path_for_loop(None, matrix, base_path)` 应直接返回 `base_path`。
- Gate 调用处：若 `parse_loop_state(...)` 返回 `None`，则跳过 loop 解析，使用 base matrix。

### 1.4 原则

- **Fail-safe**：解析失败不阻断决策，系统继续使用 base matrix 做出决策。
- **无静默吞错**：verbose 模式下应 trace 解析失败原因（见第 4 节），便于调试。

---

## 2. loop_policy 中 matrix path 的解析规则

### 2.1 固定规则

**`churn_matrix_path` 与 `converged_matrix_path` 均按「相对 repo root」解析。**

### 2.2 说明

- 与现有 `get_matrix_path()` 行为一致：`config.py` 中 `get_matrix_path("matrices/v0.1.yaml")` 即 `_PROJECT_ROOT / "matrices/v0.1.yaml"`。
- 与 `load_matrix("matrices/pr_loop_demo.yaml")` 的调用约定一致。
- 不采用「相对当前 matrix 文件」：避免矩阵移动或嵌套目录时路径失效，且与项目现有路径约定统一。

### 2.3 合法示例

```yaml
loop_policy:
  churn_matrix_path: "matrices/pr_loop_churn.yaml"
  converged_matrix_path: "matrices/pr_loop_phase_e.yaml"
```

或仅文件名（由 `get_matrix_path` 解析到 `MATRICES_DIR`）：

```yaml
loop_policy:
  churn_matrix_path: "pr_loop_churn.yaml"
  converged_matrix_path: "pr_loop_phase_e.yaml"
```

### 2.4 无效 path 处理

- 若 `resolve_effective_matrix_path_for_loop` 返回的 path 在 `load_matrix()` 时触发 `FileNotFoundError`，由 gate 层按现有逻辑抛出 `RuntimeError`（与「矩阵文件不存在」一致）。
- `resolve_effective_matrix_path_for_loop` 不校验 path 是否存在，只做字符串解析与返回。

---

## 3. resolve_effective_matrix_path_for_loop 的职责边界

### 3.1 纯函数

**是**。该函数为纯函数：

- 输入：`(loop_state: Optional[LoopState], matrix: Matrix, base_path: str)`
- 输出：`str`（effective matrix path）
- 无副作用：不修改全局状态、不执行 I/O、不写 trace、不写 log。

### 3.2 职责范围

**仅负责**：`loop_policy` + `loop_state` → effective path 的解析。

| 职责 | 归属 |
|------|------|
| 读取 `matrix.data.get("loop_policy")` | `resolve_effective_matrix_path_for_loop` |
| 根据 `round_index`、`nit_only_streak` 与 policy 计算 effective path | `resolve_effective_matrix_path_for_loop` |
| 返回 path 字符串 | `resolve_effective_matrix_path_for_loop` |
| trace / logging | **gate.py**（调用方） |
| fallback（loop_state 解析失败时用 base） | **gate.py**（在调用前判断 `loop_state is None` 则跳过） |
| path 存在性校验、load_matrix | **gate.py**（沿用现有逻辑） |
| 对 loop_state 的 repair / 默认值填充 | **不提供**；解析失败即 fallback，不做修复 |

### 3.3 不承担的职责

- 不写 trace
- 不写 log
- 不执行 fallback repair（如补全缺失字段）
- 不校验返回的 path 是否存在
- 不加载或解析其他 matrix 文件

---

## 4. 建议的 verbose trace 字段

### 4.1 追加位置

在现有 `[TRACE] 0. Profile → Matrix` 之后，新增 `[TRACE] 0.1 Loop-Aware Matrix Routing`（若发生 loop 解析）。

### 4.2 最小字段集

| 字段 | 条件 | 示例 |
|------|------|------|
| `loop_state` | 有 loop_state 且解析成功 | `round_index=2, nit_only_streak=3` |
| `loop_state_parse_failed` | 有 loop_state 但解析失败 | `loop_state_parse_failed=True, reason=missing_key` |
| `loop_policy_present` | matrix 有 loop_policy | `loop_policy_present=True` |
| `effective_matrix_path` | 发生 loop 解析且 path 与 base 不同 | `effective_matrix_path=matrices/pr_loop_phase_e.yaml` |
| `loop_routing_reason` | path 发生切换时 | `loop_routing_reason=converged` 或 `churn` |

### 4.3 建议的 trace 行格式

**场景 A：无 loop_state**
- 不追加 trace（保持与现有一致）

**场景 B：有 loop_state，无 loop_policy**
```
[TRACE] 0.1 Loop-Aware Matrix: loop_state=round_index=0,nit_only_streak=0, loop_policy_present=False, effective_matrix_path=matrices/pr_loop_demo.yaml (unchanged)
```

**场景 C：有 loop_state，有 loop_policy，path 未切换**
```
[TRACE] 0.1 Loop-Aware Matrix: loop_state=round_index=1,nit_only_streak=0, loop_policy_present=True, effective_matrix_path=matrices/pr_loop_demo.yaml (unchanged)
```

**场景 D：有 loop_state，有 loop_policy，path 切换到 converged**
```
[TRACE] 0.1 Loop-Aware Matrix: loop_state=round_index=2,nit_only_streak=3, loop_policy_present=True, effective_matrix_path=matrices/pr_loop_phase_e.yaml, loop_routing_reason=converged
```

**场景 E：有 loop_state，有 loop_policy，path 切换到 churn**
```
[TRACE] 0.1 Loop-Aware Matrix: loop_state=round_index=5,nit_only_streak=0, loop_policy_present=True, effective_matrix_path=matrices/pr_loop_churn.yaml, loop_routing_reason=churn
```

**场景 F：loop_state 解析失败**
```
[TRACE] 0.1 Loop-Aware Matrix: loop_state_parse_failed=True, effective_matrix_path=matrices/pr_loop_demo.yaml (fallback)
```

### 4.4 实现归属

Trace 的追加在 **gate.py** 中完成，调用 `resolve_effective_matrix_path_for_loop` 后根据返回值与 `loop_state` 状态写入。`resolve_effective_matrix_path_for_loop` 不接收 trace 参数，不参与 trace 写入。

---

## 5. 总结

| 主题 | 约定 |
|------|------|
| loop_state 解析失败 | Fallback 到 base matrix，不抛异常 |
| loop_policy path | 相对 repo root，与 `get_matrix_path` 一致 |
| resolve_effective_matrix_path_for_loop | 纯函数，仅做 path 解析，无 trace/log/fallback |
| verbose trace | 由 gate.py 追加，最小字段集见第 4 节 |
