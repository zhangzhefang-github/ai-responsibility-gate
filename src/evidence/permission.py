import yaml
from ..core.models import Evidence, GateContext
from ..core.config import get_config_path
from ._action_routing import infer_action_type_from_text

with open(get_config_path("permission_policies.yaml"), encoding="utf-8") as f:
    PERMISSION_POLICIES = yaml.safe_load(f)

ACTION_PERMISSIONS = PERMISSION_POLICIES.get("action_permissions", {})

async def collect(ctx: GateContext) -> Evidence:
    """
    Permission evidence provider (decoupled from routing/tool_id).

    Based on abstract action_type, not concrete tool_id.
    This maintains Evidence independence - routing signals don't pollute permission checks.

    Action type inference:
    1. Explicit action_type from context (highest priority)
    2. Inferred from text using shared routing logic (fallback)
    3. Default to READ (safe default)
    """
    user_role = ctx.context.get("role", "normal_user") if ctx.context else "normal_user"

    # Get action_type: explicit context > inference > default
    if ctx.context and "action_type" in ctx.context:
        action_type = ctx.context["action_type"]
    else:
        # Use shared inference logic (same as ToolEvidence)
        action_type = infer_action_type_from_text(ctx.text)

    # Check permission based on action_type
    has_access = False
    reason_code = "PERMISSION_OK"

    action_config = ACTION_PERMISSIONS.get(action_type, {})
    allowed_roles = action_config.get("default_roles", [])
    restricted_roles = action_config.get("restricted", [])

    # Permission logic
    if user_role in allowed_roles:
        has_access = True
        reason_code = "PERMISSION_OK"
    elif user_role in restricted_roles:
        has_access = False
        reason_code = "ERR_IAM_ACTION_RESTRICTED"
    else:
        # Unknown role/action combination - fail closed
        has_access = False
        reason_code = "ERR_IAM_UNKNOWN_ROLE"

    return Evidence(
        provider="permission",
        available=True,
        data={
            "has_access": has_access,
            "user_role": user_role,
            "action_type": action_type,
            "reason_code": reason_code
        }
    )
