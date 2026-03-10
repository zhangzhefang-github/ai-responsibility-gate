# AI Agent Governance Roadmap

> AI Responsibility Gate = AI Agent Governance Control Plane

---

## 1. 项目定位

**AI Responsibility Gate** 是 **AI Agent Governance Control Plane**（治理控制面）：集中决策、策略外置，可类比 Kubernetes admission control、OPA-style policy engine。

核心问题：在给定上下文中，是否允许某个 agent 执行某个动作？

- Loop / churn → 是否允许继续自动循环
- Scope request → 是否允许该 scope
- Tool misuse → 是否允许该 tool call
- Hallucinated actions → 是否允许采信该动作声明

---

## 2. 三层架构

```
Signal Layer
    │  (domain, signal_type, payload)
    ▼
Evidence Providers
    │  RiskProvider | PermissionProvider | ToolEvidenceProvider | ...
    ▼
AI Responsibility Gate
    │  signal → evidence → matrix → decision
    ▼
Decision (ALLOW / ONLY_SUGGEST / HITL / DENY)
```

| 层级 | 职责 |
|------|------|
| **Signal Layer** | 统一输入格式。Gate 不解析 payload。 |
| **Evidence Providers** | 插件式，按 domain 提供 evidence 标准字段。 |
| **AI Responsibility Gate** | 只依赖 evidence 标准字段，裁决逻辑稳定。 |

**扩展路径：** 新 domain = 新 Signal + 新 EvidenceProvider，Gate 核心不变。

---

## 3. Phase Roadmap

| Phase | 内容 | 状态 |
|-------|------|------|
| **Phase 1** | PR loop governance | ✅ Completed |
| **Phase 2** | Permission governance | ✅ Minimal validation completed |
| **Phase 3** | Tool governance | 规划中 |
| **Phase 4** | Hallucinated action verification | 规划中 |
| **Phase 5+** | Runtime integration / observability | 规划中 |

### 已验证 Domain 概要

- **Domain 1: PR loop** — RiskProvider，8/8 replay 通过
- **Domain 2: Permission** — PermissionEvidenceProvider，2/2 replay 通过（read→ALLOW, admin→HITL）
- **Gate core** 未改动；新 domain 通过 **Signal + EvidenceProvider** 接入

### Phase 1：PR loop governance（已完成）

- Signal domain: `pr`（review_bug, ci_failure, maintainer_intervention, nit_only）
- EvidenceProvider: RiskProvider
- Replay: 8/8 rounds 通过
- Loop-aware matrix routing: nit_only_streak → converged, round_index → churn

### Phase 2：Permission governance（最小验证已完成）

- Signal domain: `permission`（scope_request）
- EvidenceProvider: PermissionEvidenceProvider
- Replay: 2/2 rounds 通过（case_001_scope_read, case_002_scope_admin）
- 目标：权限边界裁决（read→ALLOW, write→ONLY_SUGGEST, admin→HITL）

### Phase 3：Tool governance（规划中）

- Signal domain: `tool`（tool_call）
- EvidenceProvider: ToolEvidenceProvider
- 目标：tool call 治理

### Phase 4：Hallucinated action verification（规划中）

- Signal domain: `action`（claim）
- EvidenceProvider: VerificationProvider
- 目标：可验证性治理

### Phase 5+：Runtime integration / observability（规划中）

- 目标：运行时集成、可观测性、生产环境部署
