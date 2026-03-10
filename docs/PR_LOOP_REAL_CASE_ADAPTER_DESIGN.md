# Task 2: PR Loop Real Case Adapter 设计

> 使 `cases/pr_loop_real/*.json` 可在不大改 core 的前提下回放。  
> 背景：case 中 PR 域信号（FUNCTIONAL_CORRECTNESS、REVIEW_LOGIC_BUG 等）不在 signals_catalog，直接 replay 会映射为 UNKNOWN_SIGNAL（R1）。

---

## 1. 方案对比

### 方案 A：Adapter 映射优先

**思路**：在 replay 入口前，用 adapter 将 PR 域 signals 映射为项目已识别的 signals，再调用 core_decide。

| 维度 | 说明 |
|------|------|
| **Core 改动** | 无 |
| **signals_catalog 改动** | 无 |
| **新增** | adapter 模块 + PR loop replay 脚本 |
| **映射表** | 硬编码或 YAML：PR_signal → project_signal |
| **边界** | 部分 PR 信号无语义等价（如 MAINTAINER_INTERVENTION），需用「代理信号」 |

**优点**：
- core 完全不动
- catalog 保持精简
- 映射可配置、可迭代
- 适配不同 PR 工具链（Greptile、CodeRabbit 等）的 signal 命名

**缺点**：
- MAINTAINER_INTERVENTION 等无直接等价信号，需用 BUILD_CHAIN 等代理，语义失真
- 每增加新 PR 信号需维护映射表
- 映射逻辑与 catalog 可能长期分叉

---

### 方案 B：直接扩充 signals_catalog.yaml

**思路**：把 PR 域信号加入 catalog，由现有 normalize_signals + risk 链路处理。

| 维度 | 说明 |
|------|------|
| **Core 改动** | 无 |
| **signals_catalog 改动** | 新增 6+ 条 PR 信号 |
| **risk.py 改动** | 需扩展 signal→risk 映射 |
| **新增** | 仅 PR loop replay 脚本 |

**优点**：
- 信号语义清晰，MAINTAINER_INTERVENTION 可单独定义为 R3
- 与现有 catalog 体系一致
- 长期可维护

**缺点**：
- catalog 迅速膨胀，PR 专属信号与通用信号混在一起
- risk.py 需改（或通过 default_risk_floor 自动推导，若支持）
- 不同 PR 工具链信号命名不一，易产生大量「别名」条目

---

## 2. 推荐方案：**A（Adapter 优先）**

**理由**：

1. **符合约束**：不改 core 主链路，不立刻扩充 catalog。
2. **职责清晰**：adapter 负责「PR 域 → 项目域」的转换，catalog 保持通用。
3. **可演进**：先靠映射表跑通 replay；若某 PR 信号被广泛使用，再考虑进 catalog。
4. **工具链隔离**：Greptile、CodeRabbit 等信号命名不同，adapter 可各自维护映射，catalog 不受影响。

**折中**：对 MAINTAINER_INTERVENTION 等「人类介入」类信号，adapter 映射到 BUILD_CHAIN（代理 R3→HITL），并在文档中注明为已知语义近似。

---

## 3. 建议新增文件与职责

### 3.1 新增文件

| 文件 | 职责 |
|------|------|
| `src/replay/pr_loop_adapter.py` | PR 域 signal → 项目 signal 映射；round → DecisionRequest 构造 |
| `config/pr_loop_signal_map.yaml` | 可选的 PR signal 映射表（adapter 可先硬编码，后续迁出） |
| `src/replay/run_pr_loop.py` | PR loop real case 的 replay 入口（读 case、调 adapter、调 decide、写报告） |

### 3.2 不修改

- `src/core/*`
- `src/evidence/*`
- `examples/pr_gate_ai_review_loop/signals_catalog.yaml`
- `src/replay/run.py`（保留现有 text-based replay）

---

## 4. 函数签名与映射边界

### 4.1 Adapter 函数签名

```
def map_pr_signals_to_project_signals(
    pr_signals: list[str],
    maintainer_intervened: bool = False,
    ci_status: str | None = None,
) -> list[str]:
    """
    将 PR 域 signals 映射为项目已识别 signals。

    - pr_signals: case round 中的 signals 列表
    - maintainer_intervened: 若为 True，注入代理信号以触发 HITL
    - ci_status: 可选，用于 CI_FAILURE 等信号的上下文

    Returns:
        映射后的 signals，均为 signals_catalog 中的名称。
    """
```

```
def round_to_decision_request(
    round_data: dict,
    case_id: str,
) -> tuple[DecisionRequest, str]:
    """
    将 case 的单个 round 转为 DecisionRequest + matrix_path。

    - round_data: round 对象（含 loop_state, signals, ci_status, maintainer_intervened 等）
    - case_id: 用例 ID，用于 request_id 等

    Returns:
        (DecisionRequest, matrix_path)
    """
```

### 4.2 映射表（建议先硬编码在 adapter 内）

| PR Signal | Project Signal | 说明 |
|-----------|----------------|------|
| FUNCTIONAL_CORRECTNESS | BUG_RISK | 功能正确性 → 潜在缺陷 |
| REVIEW_LOGIC_BUG | BUG_RISK | 逻辑问题 |
| TEST_MISSING | BUG_RISK | 缺测，保守视为 R2 |
| CI_FAILURE | BUG_RISK | CI 失败多为可修复问题，保守用 R2；若需 R3 可改为 BUILD_CHAIN |
| HUMAN_OVERRIDE | （见下） | 与 MAINTAINER_INTERVENTION 合并处理 |
| MAINTAINER_INTERVENTION | BUILD_CHAIN | 代理：人类介入 → 需 HITL，用 R3 代理 |
| （未在表中） | UNKNOWN_SIGNAL | 保持保守 |

**maintainer_intervened=True 时**：无论 pr_signals 内容，在映射结果中追加 `BUILD_CHAIN`，以触发 R3→HITL。

### 4.3 映射边界

| 边界 | 约定 |
|------|------|
| **输入** | 仅处理 case schema 中的 `rounds[].signals`、`maintainer_intervened`、`ci_status` |
| **输出** | 仅输出 signals_catalog 中已有信号 |
| **不处理** | review_comments 的 type/source 等，不参与映射 |
| **ci_status** | 当前仅作元数据；若未来用 CI 影响决策，可在 adapter 中根据 ci_status 注入 BUILD_CHAIN 等 |
| **expected_decision** | 不参与映射，仅用于 replay 校验 |

---

## 5. Replay 流程

```
1. 读取 cases/pr_loop_real/*.json
2. 对每个 round:
   a. map_pr_signals_to_project_signals(round.signals, round.maintainer_intervened, round.ci_status)
   b. round_to_decision_request(round, case_id) → req, matrix_path
   c. core_decide(req, matrix_path)
   d. 比较 predicted vs expected_decision
3. 汇总报告
```

---

## 6. case_001 预期映射结果

| Round | PR Signals | maintainer_intervened | 映射后 | 预期 risk | 预期 decision |
|-------|-------------|------------------------|--------|-----------|---------------|
| 0 | FUNCTIONAL_CORRECTNESS, REVIEW_LOGIC_BUG, TEST_MISSING | false | BUG_RISK | R2 | ONLY_SUGGEST |
| 1 | CI_FAILURE, FUNCTIONAL_CORRECTNESS | false | BUG_RISK | R2 | ONLY_SUGGEST |
| 2 | HUMAN_OVERRIDE, MAINTAINER_INTERVENTION | true | BUILD_CHAIN | R3 | HITL |

**说明**：Round 1 将 CI_FAILURE 映射为 BUG_RISK（R2），以匹配 case 的 expected_decision=ONLY_SUGGEST。若业务期望 CI 失败即 HITL，可将 CI_FAILURE 改为映射为 BUILD_CHAIN。设计阶段建议：先实现映射与 replay，再根据 case_001 实际结果迭代映射规则。
