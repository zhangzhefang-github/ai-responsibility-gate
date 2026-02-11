from src.core.matrix import resolve_matrix_path


def test_profile_to_matrix_resolution():
    default = "matrices/v0.1.yaml"

    # No profile → default
    assert resolve_matrix_path(None, default) == default

    # Unknown profile → default
    assert resolve_matrix_path("unknown_profile", default) == default

    # Known demo profile → mapped matrix
    assert resolve_matrix_path("pr_review_loop", default) == "matrices/pr_loop_demo.yaml"

from src.core.matrix import resolve_matrix_path


def test_profile_matrix_resolve_default_and_known_profile():
    """
    验证 profile → matrix 解析逻辑：
    - 无 profile / None / 未知 profile → 使用默认 matrix_path
    - 已知 profile（pr_review_loop）→ 使用 pr_loop_demo 矩阵
    """
    default_path = "matrices/v0.1.yaml"

    # 无 profile
    assert resolve_matrix_path(None, default_path) == default_path

    # 空字符串 profile
    assert resolve_matrix_path("", default_path) == default_path

    # 未知 profile
    assert resolve_matrix_path("unknown_profile", default_path) == default_path

    # 已知 demo profile
    assert resolve_matrix_path("pr_review_loop", default_path) == "matrices/pr_loop_demo.yaml"

