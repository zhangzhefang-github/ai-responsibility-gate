# Phase A: PR Gate AI Review Loop 示例

> **目标：复现问题 + 可演示收敛（不改 core）**

## 概述

这个示例演示了如何使用 Gate + Loop Guard 解决 **AI coding × AI review 无限循环**的问题。

### 核心问题

- 团队 PR 数量很大，AI reviewer 会提出大量建议
- 其中很多是吹毛求疵/风格类建议（70% nit/style）
- 导致 coding agent 反复修改，出现新的问题，陷入无限循环

### 解决方案

- **AI 只输出 signals + evidence**（ReviewComment → AISignal）
- **Gate 输出唯一裁决**（ALLOW / ONLY_SUGGEST / HITL / DENY）
- **Loop Guard**：通过 LoopState（round_index, nit_only_streak）+ profile/matrix 收敛，而不是让 AI 自己决定停

---

## 文件结构

```
examples/pr_gate_ai_review_loop/
├── __init__.py
├── models.py              # PRMeta, ReviewComment, AISignal 模型
├── ai_reviewer_stub.py    # AI Reviewer 模拟器（70% nit/style）
├── ai_coding_stub.py      # AI Coding 模拟器（修复代码，可能引入新问题）
├── signal_extractor.py    # 从 ReviewComment 提取 AISignal
├── pr_gate.py             # PR Gate 决策逻辑（独立实现，不改 core）
├── demo.py                # Demo Runner（3 个场景）
└── README.md              # 本文档
```

---

## 如何运行

### 前置条件

```bash
# 确保在项目根目录
cd /path/to/ai-responsibility-gate

# 安装依赖（如果还没有）
pip install -r requirements.txt
```

### 运行 Demo

```bash
# 运行 3 个场景
python examples/pr_gate_ai_review_loop/demo.py
```

### 预期输出

Demo 会运行 3 个场景：

1. **Scenario A: 低风险 docs/test-only PR**
   - 预期：直接 ALLOW 或经过 1-2 轮后 ALLOW（Stop Condition）

2. **Scenario B: 中风险 small change 但 touching non-sensitive**
   - 预期：ONLY_SUGGEST 或经过 2-3 轮后 ALLOW（Stop Condition）

3. **Scenario C: 高风险 touching auth/build/CI/deps**
   - 预期：HITL（需要人工介入）

每个场景会打印：
- AI Signals: 从 ReviewComment 提取的信号（profile 层）
- Risk Level: 基于 signals 识别的风险等级（解释用，不参与控制流）
- Gate Decision: ALLOW / ONLY_SUGGEST / HITL / DENY（唯一裁决源）
- Primary Reason & Explanation: Gate 给出的裁决理由与摘要解释

---

## 核心逻辑

### 1. AI Reviewer Stub

```python
# 生成 ReviewComment，70% 概率是 style/nit
comments = generate_review_comments(pr_meta, round_index)
```

**策略：**
- 70% 概率生成 style/nit 类评论
- 如果 touching sensitive boundary，增加 security 评论概率
- round_index 越高，nit 越多（模拟越改越糟）

### 2. AI Coding Stub

```python
# 根据 review comments 应用修复
pr_meta = apply_fixes(pr_meta, comments)
```

**策略：**
- 修复 bug/security/build 类评论（降低风险）
- 修复 style/nit 类评论，但有 30% 概率引入新的 nit（模拟越改越糟）

### 3. Signal Extractor

```python
# 从 ReviewComment 提取归一化的 AISignal
signals = extract_signals(comments)
```

**规则：**
- security 评论 → `SECURITY_BOUNDARY`
- build 评论 → `BUILD_CHAIN`
- bug 评论（高 severity） → `BUG_RISK`
- style/nit 评论 → `LOW_VALUE_NITS`

### 4. Gate 决策（Phase C / Phase D 之后）

```python
# Gate 决策（确定性规则，来自 core gate）
core_req = DecisionRequest(
    text="pr_loop_guard_demo",
    structured_input={"profile": "pr_review_loop", "signals": [...]},
    context={"loop_state": {...}},
)
response = await core_decide(core_req)
```

**要点：**
- 每一轮只有 **一个权威决策源**：`core_decide` 返回的 Decision
- 示例层只负责：
  - 计算 LoopState（round_index, nit_only_streak）
  - 提取 AI Signals 并写入 structured_input["signals"]
  - 通过 structured_input["profile"] 选择矩阵（profile → matrix）
  - 打印解释性信息（AI Signals / Risk Level / Gate Decision）

---

## 示例输出（示意）

```
############################################################
# Scenario: A) Low Risk: docs/test-only PR
############################################################
Initial PR Meta:
  - Files changed: 2
  - LOC added: 50
  - Touched paths: ['docs/README.md', 'tests/test_example.py']
  - Touches sensitive boundary: False
  - Has CI green: True
  - Contributor trust level: known

[Round 1] AI Reviewer generated 3 comments:
  1. [nit] (severity=1) 变量命名可以更清晰
  2. [style] (severity=2) 代码风格不符合项目规范
  3. [nit] (severity=1) 建议添加空行以提高可读性

============================================================
Round 1
============================================================
AI Signals (profile): ['LOW_VALUE_NITS']
Risk Level (explain-only): R0
Gate Decision: ONLY_SUGGEST
Primary Reason: DEFAULT_DECISION
Explanation Summary: Suggestion-only response with disclaimer required
============================================================

[Round 1] AI Coding applying fixes...

[Round 2] AI Reviewer generated 4 comments:
  1. [nit] (severity=1) 建议添加注释
  2. [style] (severity=2) 缩进不一致
  3. [nit] (severity=1) 可以简化这个表达式
  4. [nit] (severity=1) 建议使用更描述性的变量名

============================================================
Round 2
============================================================
AI Signals (profile): ['LOW_VALUE_NITS']
Risk Level (explain-only): R0
Gate Decision: ALLOW
Primary Reason: PR_LOOP_BENIGN_STREAK
Explanation Summary: Request approved for direct answer
============================================================

✅ PR Approved! Stopping after 2 rounds.
```

---

## 关键设计决策

### 1. 不改 core

- 所有代码都在 `examples/pr_gate_ai_review_loop/` 目录下
- 不修改 `src/core/` 中的任何文件
- 独立实现 PR Gate 决策逻辑

### 2. 最小可用模型

- `PRMeta`: PR 元数据
- `ReviewComment`: AI Reviewer 的评论
- `AISignal`: 归一化的信号（从 ReviewComment 提取）

### 3. LoopGuard 与收敛策略

- LoopState 只通过 `context["loop_state"]` 进入 core（例如 round_index, nit_only_streak）
- Stage 5.5 LoopGuard 是 core 的一等能力（默认 no-op，tighten-only）
- 收敛策略（如「多轮 benign → 放行」）通过 profile + matrix 表达，而不是写死在 risk 层或 demo 里

### 4. 确定性规则

- Gate 规则是确定性的，不依赖真实 LLM 或 GitHub PR
- AI 只输出 signals + evidence，Gate 做最终决策

---

## Phase E: Governance Demonstration

This demo proves that even if the AI reviewer and AI coder oscillate or regress,
the system remains stable by centralizing decision authority in the Gate.

- The AI reviewer may keep producing low-value nits or even new issues.
- The AI coder may keep modifying code and sometimes make things worse.
- The Gate is the **only** component that decides:
  - when to ALLOW a PR,
  - when to escalate to HITL (Human-in-the-Loop),
  - when to continue with ONLY_SUGGEST.
- Once the Gate returns HITL or ALLOW (under the `pr_review_loop` profile),
  the AI loop is terminated and cannot continue by itself.

换句话说：**即使 AI 在「自嗨」地互相挑刺，系统也不会失控——最终说「行 / 不行」的是 Gate，而不是 AI 本身。**

---

## Phase E+: Signals 字典治理与“规则不会爆炸”

本示例还演示了一个关键的治理能力：**上游 AI 输出被收敛为有限的 Signals 字典**，而不是直接输出规则或任意字符串。

- Signals 定义在 `signals_catalog.yaml` 中：
  - 每个 signal 有 `name` / `description` / `evidence_examples` / `default_risk_floor`
  - 例如：`SECURITY_BOUNDARY` / `BUILD_CHAIN` / `BUG_RISK` / `LOW_VALUE_NITS` / `UNKNOWN_SIGNAL` / `MULTI_SIGNAL`
- 示例层通过 `normalize_signals(...)` 做：
  - 去重 + 排序（保证确定性输出）
  - 过滤非字符串、空字符串
  - 不在 allowlist 的值统一映射为 `UNKNOWN_SIGNAL`（fail-closed）
- risk 只做 **静态证据 + 上调（tighten-only）**：
  - 从 `structured_input["signals"]` 推导 `risk_level`（R0–R3）
  - 永远不做“降级”或“收敛”语义
- 差异化策略放在 `profile → matrix`：
  - 不同 profile（例如 `pr_review_loop`）可以绑定不同矩阵文件
  - 建议每个 profile 的规则数量控制在 ≤ 30 条，保持可审计、可维护

因此：

- **规则不会爆炸**：因为 Gate 只看有限集的抽象 signals + 矩阵配置，不直接暴露在海量、不可控的 reviewer 文本之下。
- **上游 AI 也容易接入**：AI 只需要输出我们定义好的 signals（或映射为 UNKNOWN_SIGNAL），不需要“写规则引擎”。

### 新增一个 signal 的最小改动步骤（工程视角）

1. 在 `examples/pr_gate_ai_review_loop/signals_catalog.yaml` 中增加一条新 signal：
   - 填写 `name` / `description` / `evidence_examples` / `default_risk_floor`
2. 在 `signal_extractor.py` 中增加一条映射规则，或在 reviewer stub 的样本中生成能触发该 signal 的评论。
3. （可选）在 `matrices/pr_loop_demo.yaml` 或其他 profile 对应矩阵中增加一条规则，指定该 signal 组合下的决策。

**不需要**：

- 修改 `src/core/*` 或 `src/evidence/*` 的生产逻辑
- 把 PR/GitHub/diff 语义塞进 core
- 在 demo 里再加一套"本地决策机"

---

## Phase E (Enhanced): Governance Demonstration for Technical Experts

### Overview

Phase E demonstrates a **configurable convergence policy** where the decision to ALLOW a PR after N consecutive benign rounds is expressed through **matrix path switching**, not hardcoded in demo code.

**Important:** No modifications to `src/core/*` or `src/evidence/*` are required. All policy configuration stays in the `examples/` layer.

### Key Architectural Principle

**Convergence point is policy-configurable, not hardcoded.**

- Demo layer (`demo_phase_e.py`) switches `matrix_path` based on `nit_only_streak`
- Round 1-2: `matrix_path="matrices/pr_loop_demo.yaml"` → ONLY_SUGGEST (default)
- Round 3+: `matrix_path="matrices/pr_loop_phase_e.yaml"` → ALLOW
- Risk layer (`src/evidence/risk.py`) remains unchanged - only does semantic folding
- Gate is the **only** decision authority throughout the entire loop

### How It Works

1. **Demo Layer**: Counts consecutive benign rounds (`nit_only_streak`)
2. **Threshold Reached**: When `nit_only_streak >= BENIGN_STREAK_THRESHOLD` (default: 3)
3. **Matrix Path Switch**: Demo changes `matrix_path` from "matrices/pr_loop_demo.yaml" to "matrices/pr_loop_phase_e.yaml"
4. **Gate Decision**: Core gate (`core_decide`) loads the specified matrix and returns `ALLOW`, terminating the loop

### Why This Matters

This demonstrates that:
- The threshold N (consecutive rounds) can be changed by modifying `BENIGN_STREAK_THRESHOLD` in demo code
- The actual decision (ALLOW) is controlled by matrix configuration, not demo code
- No modifications to `src/core/*` or `src/evidence/*` required
- Gate is the **only** decision authority throughout the entire loop

### Running Phase E Demo

```bash
# From project root directory
python examples/pr_gate_ai_review_loop/demo_phase_e.py
```

### Expected Output

#### Scenario 1: Benign (docs-only rename)

```
[Round 1] AI Reviewer generated 1 comments:
  1. [style] (severity=1) 建议添加类型注解

============================================================
Round 1
============================================================
Matrix: matrices/pr_loop_demo.yaml
AI Raw Signals (extractor): ['LOW_VALUE_NITS']
AI Normalized Signals (allowlisted): ['LOW_VALUE_NITS']
Risk Level (explain-only): R0
Gate Decision: ONLY_SUGGEST
Primary Reason: DEFAULT_DECISION
(Explain-only) Risk evidence computed for display; decision authority remains in the core gate.
============================================================

[Round 2] Matrix: matrices/pr_loop_demo.yaml → ONLY_SUGGEST

[Round 3]
============================================================
Matrix: matrices/pr_loop_phase_e.yaml
AI Raw Signals (extractor): ['LOW_VALUE_NITS']
AI Normalized Signals (allowlisted): ['LOW_VALUE_NITS']
Risk Level (explain-only): R0
Gate Decision: ALLOW
Primary Reason: PR_LOOP_CONVERGED
============================================================

✅ Gate Decision: ALLOW - Gate terminated the loop
   (Converged after 3 benign rounds, matrix: matrices/pr_loop_phase_e.yaml)
```

#### Scenario 2: Loop-churn (AI oscillates)

```
[Round 1] Matrix: matrices/pr_loop_demo.yaml → ONLY_SUGGEST
[Round 2] Matrix: matrices/pr_loop_demo.yaml → ONLY_SUGGEST
[Round 3] Matrix: matrices/pr_loop_demo.yaml → ONLY_SUGGEST
[Round 4] Matrix: matrices/pr_loop_demo.yaml → ONLY_SUGGEST
[Round 5] Matrix: matrices/pr_loop_demo.yaml → ONLY_SUGGEST

⚠️  Max rounds (5) reached. Loop terminated by max_rounds limit.
```

#### Scenario 3: High-risk (touches build/auth)

```
============================================================
Round 1
============================================================
Matrix: matrices/pr_loop_demo.yaml
AI Raw Signals (extractor): ['BUILD_CHAIN', 'LOW_VALUE_NITS', 'SECURITY_BOUNDARY']
AI Normalized Signals (allowlisted): ['BUILD_CHAIN', 'LOW_VALUE_NITS', 'SECURITY_BOUNDARY']
Risk Level (explain-only): R3
Gate Decision: HITL
Primary Reason: PR_LOOP_HIGH_RISK
============================================================

⚠️  Gate Decision: HITL - Gate terminated the loop
   (High-risk signals detected, human intervention required)
```

### Running Tests

```bash
# Run all demo contract tests
pytest tests/test_demo_contract_smoke.py -v

# Run all related tests
pytest tests/test_signals_catalog_loadable.py tests/test_signals_normalization.py tests/test_demo_contract_smoke.py -v
```

### Files Modified/Created for Phase E

| File | Type | Description |
|------|------|-------------|
| `demo_phase_e.py` | NEW | Enhanced demo with matrix path switching |
| `matrices/pr_loop_phase_e.yaml` | NEW | Matrix for converged loop state |
| `tests/test_demo_contract_smoke.py` | NEW | Regression tests for signal chain contract |
| `README.md` | MODIFIED | This section |

**Note:** `src/core/*` and `src/evidence/*` were NOT modified - all policy stays in examples/ layer.
