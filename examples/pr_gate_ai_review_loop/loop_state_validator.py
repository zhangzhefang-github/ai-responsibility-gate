"""
LoopState Validator (Examples Layer Only)

提供最小化的 loop_state 校验，确保在调用 core_decide 前数据结构正确。

重要设计约束：
- 此校验在 examples/ 层，不修改 src/core/*
- 不注入强类型到 core（core 保持 repo-agnostic）
- 仅在 demo 层使用，生产环境可有选择地启用
"""
from typing import Any, Dict


class LoopStateValidationError(ValueError):
    """LoopState 校验失败异常"""
    pass


def validate_loop_state(
    loop_state: Any,
    max_rounds: int,
) -> Dict[str, Any]:
    """
    校验 loop_state 结构是否符合预期。

    校验规则：
    1. loop_state 必须是 dict
    2. round_index 必须存在且为 int，范围：0 <= round_index <= max_rounds
    3. nit_only_streak 必须存在且为 int，范围：nit_only_streak >= 0
    4. max_rounds 必须 > 0

    Args:
        loop_state: 待校验的 loop_state 对象
        max_rounds: 最大轮次阈值

    Returns:
        校验后的 loop_state（如果合法）

    Raises:
        LoopStateValidationError: 如果校验失败
    """
    # 规则 1: 必须是 dict
    if not isinstance(loop_state, dict):
        raise LoopStateValidationError(
            f"loop_state must be dict, got {type(loop_state).__name__}"
        )

    # 规则 4: max_rounds 必须 > 0
    if not isinstance(max_rounds, int) or max_rounds <= 0:
        raise LoopStateValidationError(
            f"max_rounds must be int > 0, got {max_rounds}"
        )

    # 规则 2: round_index 校验
    if "round_index" not in loop_state:
        raise LoopStateValidationError(
            "loop_state missing required key: 'round_index'"
        )

    round_index = loop_state["round_index"]
    if not isinstance(round_index, int):
        raise LoopStateValidationError(
            f"loop_state.round_index must be int, got {type(round_index).__name__}"
        )

    if round_index < 0:
        raise LoopStateValidationError(
            f"loop_state.round_index must be >= 0, got {round_index}"
        )

    if round_index > max_rounds:
        raise LoopStateValidationError(
            f"loop_state.round_index ({round_index}) exceeds max_rounds ({max_rounds})"
        )

    # 规则 3: nit_only_streak 校验
    if "nit_only_streak" not in loop_state:
        raise LoopStateValidationError(
            "loop_state missing required key: 'nit_only_streak'"
        )

    nit_only_streak = loop_state["nit_only_streak"]
    if not isinstance(nit_only_streak, int):
        raise LoopStateValidationError(
            f"loop_state.nit_only_streak must be int, got {type(nit_only_streak).__name__}"
        )

    if nit_only_streak < 0:
        raise LoopStateValidationError(
            f"loop_state.nit_only_streak must be >= 0, got {nit_only_streak}"
        )

    return loop_state


def validate_loop_state_relaxed(
    loop_state: Any,
    max_rounds: int,
) -> Dict[str, Any]:
    """
    宽松版本的 loop_state 校验（仅修复缺失字段，不抛异常）。

    如果字段缺失，填充默认值：
    - round_index: 0
    - nit_only_streak: 0

    用于容错场景。
    """
    if not isinstance(loop_state, dict):
        loop_state = {}

    # 填充默认值
    if "round_index" not in loop_state:
        loop_state["round_index"] = 0

    if "nit_only_streak" not in loop_state:
        loop_state["nit_only_streak"] = 0

    # 仍然校验类型和范围（但已修复缺失）
    return validate_loop_state(loop_state, max_rounds)
