# Permission Governance 实施设计 - Implementation Readiness Refinement

> 基于 [PERMISSION_GOVERNANCE_MINIMAL_DESIGN.md](PERMISSION_GOVERNANCE_MINIMAL_DESIGN.md) 的收敛版，明确 Phase 2 最小实现范围与稳定策略。

---

## 1. 稳定预期决策（无歧义）

| scope | risk_level | project_signals | 预期 decision |
|-------|------------|-----------------|---------------|
| `read` | R0 | LOW_VALUE_NITS | **ALLOW** |
| `write` | R2 | BUG_RISK | **ONLY_SUGGEST** |
| `admin` | R3 | BUILD_CHAIN | **HITL** |

**策略约束**：上述映射在 replay 中必须稳定可复现，不允许「ALLOW 或 ONLY_SUGGEST」等不确定结果。

---

## 2. Phase 2 最小实现范围

| 项目 | 是否实现 | 说明 |
|------|----------|------|
| case_001_scope_read.json | ✅ 是 | read → ALLOW |
| case_002_scope_admin.json | ✅ 是 | admin → HITL |
| case_003_mixed.json | ❌ 否 | 暂不实现，Phase 2 仅验证 read + admin 两条路径 |

---

## 3. Matrix 选择：专用 permission matrix（推荐）

### 3.1 结论

**推荐使用专用 `matrices/permission_demo.yaml`**，不复用 `pr_loop_demo.yaml`。

### 3.2 原因

| 方案 | read → ALLOW | admin → HITL | 问题 |
|------|--------------|--------------|------|
| pr_loop_demo | ❌ | ✅ | Information 默认 ONLY_SUGGEST，R0 无显式规则时走默认 → ONLY_SUGGEST |
| pr_loop_phase_e | ✅ | ✅ | 语义为「converged PR loop」，与 permission domain 无关；且需 loop_state 触发路由 |
| **permission_demo（新建）** | ✅ | ✅ | 显式 R0/ALLOW、R3/HITL 规则，语义清晰，无依赖 |

### 3.3 permission_demo.yaml 最小配置

```yaml
version: "permission_demo_v0.1"

defaults:
  Information: "ALLOW"
  RiskNotice: "ONLY_SUGGEST"
  EntitlementDecision: "HITL"

rules:
  - rule_id: "PERMISSION_R0_ALLOW"
    match:
      risk_level: "R0"
      action_types: ["READ"]
    decision: "ALLOW"
    primary_reason: "PERMISSION_READ_SCOPE"

  - rule_id: "PERMISSION_R3_HITL"
    match:
      risk_level: "R3"
      action_types: ["READ"]
    decision: "HITL"
    primary_reason: "PERMISSION_ELEVATED"

confidence_thresholds:
  low: 0.6
  very_low: 0.3

missing_evidence_policy:
  missing_risk: "tighten"
  missing_permission: "hitl"
  missing_knowledge: "tighten"

conflict_resolution:
  risk_high_overrides_permission_ok: true
  r3_with_permission_action: "hitl"
```

**说明**：
- Permission replay 的 `text` 为占位（如 `permission_replay`），无 operation 关键词 → classifier 输出 Information
- `collect_tool` 无 tool_id 时默认 `action_type="READ"`
- R0 + READ → PERMISSION_R0_ALLOW → ALLOW
- R3 + READ → PERMISSION_R3_HITL → HITL

---

## 4. 职责边界

### 4.1 permission_adapter.py

| 职责 | 包含 | 不包含 |
|------|------|--------|
| Case 解析 | 读取 `scope_request`，构造 `Signal(domain="permission", ...)` | 不解析 PR 域 signals |
| Signal 转换 | `scope_request_to_signal(scope: str) -> Signal` | 不实现 scope→risk 映射（由 Provider 负责） |
| project_signals 生成 | 调用 `signals_to_project_signals_via_evidence(signals)`，复用 `_merge_risk_level`、`_governance_evidence_to_project_signals` | 不实现合并逻辑（复用 pr_loop_adapter 或共享模块） |
| DecisionRequest 构造 | 调用 `round_to_decision_request(..., project_signals, loop_state={})` | 不实现 round_to_decision_request（复用） |
| Registry 使用 | 使用含 PermissionEvidenceProvider 的 Registry | 不注册 Provider（由模块初始化负责） |

**边界**：permission_adapter 是「permission case → Signal → project_signals → DecisionRequest」的编排层，不承载 scope→risk 的业务规则。

### 4.2 PermissionEvidenceProvider

| 职责 | 包含 | 不包含 |
|------|------|--------|
| Signal 匹配 | `supports(signal)`: `signal.domain == "permission"` | 不处理 pr、tool 等其它 domain |
| scope→evidence 映射 | 读取 `payload["scope"]`，输出 `GovernanceEvidence(risk_level, scope_level, ...)` | 不解析 case JSON、不构造 DecisionRequest |
| 映射规则 | read→R0, write→R2, admin→R3, 未知→R1 | 不依赖外部 YAML（Phase 2 硬编码即可） |

**边界**：PermissionEvidenceProvider 是「permission Signal → GovernanceEvidence」的纯转换器，无 I/O、无 Gate 依赖。

---

## 5. 复用与共享

| 组件 | 复用方式 |
|------|----------|
| `_merge_risk_level` | 从 pr_loop_adapter 提取到共享模块，或 permission_adapter 直接 import pr_loop_adapter |
| `_governance_evidence_to_project_signals` | 同上 |
| `round_to_decision_request` | 直接复用 pr_loop_adapter，permission 传 `loop_state={}` |
| `signals_to_project_signals_via_evidence` | 需使用含 PermissionEvidenceProvider 的 Registry；可扩展 pr_loop_adapter 的 `_get_registry()` 注册 PermissionProvider，或 permission_adapter 自建 Registry |

**推荐**：扩展 `_get_registry()`，同时注册 RiskProvider + PermissionEvidenceProvider；permission_adapter 与 pr_loop_adapter 共用该 Registry。这样 PR 与 Permission 可共用同一套 `signals_to_project_signals_via_evidence`，无需重复实现。

---

## 6. 新增文件清单（收敛版）

| 文件 | 职责 |
|------|------|
| `src/evidence/permission_provider.py` | PermissionEvidenceProvider |
| `src/replay/permission_adapter.py` | scope_request→Signal，复用 signals_to_project_signals、round_to_decision_request |
| `src/replay/run_permission_replay.py` | Permission replay 入口 |
| `cases/permission_real/case_001_scope_read.json` | read → ALLOW |
| `cases/permission_real/case_002_scope_admin.json` | admin → HITL |
| `matrices/permission_demo.yaml` | 专用 matrix，显式 R0/ALLOW、R3/HITL |

**不新增**：case_003_mixed.json、config/permission_scope_policy.yaml（Phase 2 硬编码 scope→risk）。

---

## 7. Case Schema（Phase 2）

### case_001_scope_read.json

```json
{
  "case_id": "case_001_scope_read",
  "domain": "permission",
  "description": "Scope read → R0 → ALLOW",
  "matrix_path": "matrices/permission_demo.yaml",
  "rounds": [
    {
      "scope_request": "read",
      "expected_decision": "ALLOW"
    }
  ]
}
```

### case_002_scope_admin.json

```json
{
  "case_id": "case_002_scope_admin",
  "domain": "permission",
  "description": "Scope admin → R3 → HITL",
  "matrix_path": "matrices/permission_demo.yaml",
  "rounds": [
    {
      "scope_request": "admin",
      "expected_decision": "HITL"
    }
  ]
}
```

---

## 8. 实施顺序（设计阶段不执行）

1. 新增 `matrices/permission_demo.yaml`
2. 新增 `PermissionEvidenceProvider`
3. 扩展 `_get_registry()` 注册 PermissionEvidenceProvider
4. 新增 `permission_adapter.py`（scope_request_to_signal，复用 signals_to_project_signals、round_to_decision_request）
5. 新增 `run_permission_replay.py`
6. 新增 `cases/permission_real/case_001_scope_read.json`、`case_002_scope_admin.json`
7. 运行 replay，验证 2/2 通过

---

## 9. 总结

| 项目 | 结论 |
|------|------|
| 预期决策 | read→ALLOW, write→ONLY_SUGGEST, admin→HITL（稳定） |
| Phase 2 范围 | 仅 case_001 + case_002，无 case_003 |
| Matrix | 专用 permission_demo.yaml |
| permission_adapter | 编排层：case→Signal→project_signals→DecisionRequest |
| PermissionEvidenceProvider | 转换层：permission Signal→GovernanceEvidence |
