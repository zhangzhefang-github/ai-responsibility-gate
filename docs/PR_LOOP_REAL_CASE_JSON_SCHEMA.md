# PR Loop Real Case JSON Schema（最小可用）

> 用于将真实 PR / reviewer / CI / maintainer 场景转换为可离线回放的测试输入。不接 GitHub API。

---

## 1. Schema 字段说明

### 1.1 顶层结构

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `case_id` | string | 是 | 用例唯一标识 |
| `description` | string | 否 | 用例描述 |
| `matrix_path` | string | 否 | 矩阵路径，默认 `matrices/pr_loop_demo.yaml` |
| `rounds` | array | 是 | 轮次列表，每轮对应一次 `core_decide` 调用 |

### 1.2 rounds[] 每轮结构

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `loop_state` | object | 是 | 当前轮 loop 状态 |
| `signals` | array of string | 是 | 归一化信号列表，与 `structured_input.signals` 一致 |
| `ci_status` | string | 否 | CI 状态：`green` / `fail` / `pending` |
| `maintainer_intervened` | boolean | 否 | 本轮是否有人工介入 |
| `expected_decision` | string | 否 | 预期决策，用于 replay 校验 |

### 1.3 loop_state 结构

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `round_index` | int, >= 0 | 是 | 当前轮次（0-based） |
| `nit_only_streak` | int, >= 0 | 是 | 连续 benign 轮次数 |

### 1.4 signals 取值

与 `signals_catalog.yaml` 一致，建议使用：

- `SECURITY_BOUNDARY`
- `BUILD_CHAIN`
- `BUG_RISK`
- `LOW_VALUE_NITS`
- `UNKNOWN_SIGNAL`
- `MULTI_SIGNAL`

### 1.5 review_comments（可选，用于审计）

若需保留原始评论用于审计：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `review_comments` | array | 否 | 原始评论列表 |

### 1.6 review_comments[] 单条结构

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `category` | string | 是 | `style` / `nit` / `bug` / `security` / `build` / `perf` |
| `severity` | int, 1-5 | 是 | 严重程度 |
| `text` | string | 是 | 评论内容 |

---

## 2. Replay 映射关系

| Schema 字段 | core_decide 输入 |
|-------------|------------------|
| `rounds[i].loop_state` | `context.loop_state` |
| `rounds[i].signals` | `structured_input.signals` |
| `text` | 固定占位如 `"pr_loop_replay"` |
| `matrix_path` | `decide(..., matrix_path=...)` |

`ci_status`、`maintainer_intervened` 仅作元数据，当前不参与 `core_decide`，可用于筛选、报告或审计。

---

## 3. 示例一：OpenClaw 风格 PR（高危）

```json
{
  "case_id": "openclaw_auth_change",
  "description": "PR 触碰 auth 边界，首轮即 HITL",
  "matrix_path": "matrices/pr_loop_demo.yaml",
  "rounds": [
    {
      "loop_state": {
        "round_index": 0,
        "nit_only_streak": 0
      },
      "signals": ["SECURITY_BOUNDARY", "BUILD_CHAIN"],
      "ci_status": "fail",
      "maintainer_intervened": false,
      "expected_decision": "HITL",
      "review_comments": [
        {
          "category": "security",
          "severity": 5,
          "text": "权限检查逻辑可能被绕过，需人工复核"
        },
        {
          "category": "build",
          "severity": 4,
          "text": "package.json 依赖版本变更需验证"
        }
      ]
    }
  ]
}
```

---

## 4. 示例二：Churn / Nit-only 循环

**场景 A：收敛**（连续 3 轮 nit-only → ALLOW）

```json
{
  "case_id": "nit_only_converge",
  "description": "连续 3 轮 nit-only 触发收敛 → ALLOW",
  "matrix_path": "matrices/pr_loop_demo.yaml",
  "rounds": [
    { "loop_state": { "round_index": 0, "nit_only_streak": 0 }, "signals": ["LOW_VALUE_NITS"], "expected_decision": "ONLY_SUGGEST" },
    { "loop_state": { "round_index": 1, "nit_only_streak": 1 }, "signals": ["LOW_VALUE_NITS"], "expected_decision": "ONLY_SUGGEST" },
    { "loop_state": { "round_index": 2, "nit_only_streak": 2 }, "signals": ["LOW_VALUE_NITS"], "expected_decision": "ONLY_SUGGEST" },
    { "loop_state": { "round_index": 3, "nit_only_streak": 3 }, "signals": ["LOW_VALUE_NITS"], "expected_decision": "ALLOW" }
  ]
}
```

**场景 B：Churn 升级**（max_rounds 达到 → HITL）

```json
{
  "case_id": "churn_max_rounds",
  "description": "round_index >= 5 触发 churn 矩阵 → HITL",
  "matrix_path": "matrices/pr_loop_demo.yaml",
  "rounds": [
    {
      "loop_state": { "round_index": 5, "nit_only_streak": 0 },
      "signals": ["LOW_VALUE_NITS"],
      "ci_status": "green",
      "maintainer_intervened": false,
      "expected_decision": "HITL"
    }
  ]
}
```

---

## 5. 最小单轮示例

```json
{
  "case_id": "minimal_single_round",
  "rounds": [
    {
      "loop_state": { "round_index": 0, "nit_only_streak": 0 },
      "signals": ["LOW_VALUE_NITS"],
      "expected_decision": "ONLY_SUGGEST"
    }
  ]
}
```
