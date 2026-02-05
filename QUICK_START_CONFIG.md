# 配置快速参考指南

> **5 分钟快速上手配置 AI Responsibility Gate**

---

## 🎯 配置流程图

```
1. 定义工具 (tools/catalog.yaml)
   ↓
2. 定义风险规则 (config/risk_rules.yaml)
   ↓
3. 定义权限策略 (config/permission_policies.yaml)
   ↓
4. 定义决策矩阵 (matrices/v0.1.yaml)
   ↓
5. 配置知识库 (config/kb_meta.yaml)
```

---

## 📝 最小配置示例

### 1. 工具目录 (`tools/catalog.yaml`)

```yaml
tools:
  - tool_id: "refund.create"
    action_type: "MONEY"
    impact_level: "I3"
    required_role: "normal_user"

routing_hints:
  - tool_id: "refund.create"
    keywords: ["退款", "退钱"]
```

### 2. 风险规则 (`config/risk_rules.yaml`)

```yaml
defaults:
  high_amount_threshold: 5000

rules:
  - rule_id: "RISK_HIGH_AMOUNT_REFUND"
    type: "threshold"
    risk_level: "R3"
    field: "amount"
    op: ">="
    value_from_default: "high_amount_threshold"
    applies_when:
      tool_ids: ["refund.create"]
```

### 3. 权限策略 (`config/permission_policies.yaml`)

```yaml
roles:
  normal_user:
    can_actions: ["READ", "WRITE", "MONEY:limited"]

action_permissions:
  MONEY:
    default_roles: ["normal_user"]
```

### 4. 决策矩阵 (`matrices/v0.1.yaml`)

```yaml
defaults:
  Information: "ONLY_SUGGEST"
  EntitlementDecision: "HITL"

rules:
  - rule_id: "MATRIX_R3_MONEY_HITL"
    match:
      risk_level: "R3"
      action_types: ["MONEY"]
    decision: "HITL"
```

---

## ✅ 验证配置

```bash
# 1. 语法检查
python3 -c "import yaml; yaml.safe_load(open('matrices/v0.1.yaml'))"

# 2. 运行测试
make test

# 3. 回放案例
make replay
```

---

## 🔍 配置检查清单

- [ ] 所有 YAML 文件语法正确
- [ ] `action_types` 在 Matrix 和 Tool Catalog 中一致
- [ ] `tool_ids` 在 Risk Rules 和 Tool Catalog 中一致
- [ ] 所有测试通过
- [ ] 案例回放 100% 准确

---

**详细配置指南请查看 [USER_GUIDE.md](USER_GUIDE.md)**
