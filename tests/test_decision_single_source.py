"""
Architecture invariant test: there must be a single Decision enum type,
defined in core, and example/profile modules must not define their own
Decision enum named \"Decision\".
"""

import inspect

from src.core import models as core_models
import examples.pr_gate_ai_review_loop.models as pr_models
import examples.pr_gate_ai_review_loop.pr_gate as pr_gate


def test_only_core_defines_Decision_enum():
    # Core defines Decision once
    assert hasattr(core_models, "Decision")
    core_decision = core_models.Decision
    assert inspect.isclass(core_decision)

    # Example-level models must NOT define a class literally named \"Decision\"
    assert not hasattr(pr_models, "Decision")

    # Example-level gate/profile modules也不能重新定义 \"Decision\" 枚举
    assert not hasattr(pr_gate, "Decision")

