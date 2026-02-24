import importlib
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("missing", [True, False])
def test_risk_rules_yaml_error_message(monkeypatch, tmp_path, missing: bool):
    """
    配置缺失/语法错误时，risk 模块抛出的错误信息中必须包含最终解析路径，
    便于快速定位配置问题。

    Patch 源头 get_config_path，避免 reload 时局部 monkeypatch 被覆盖。
    """
    # 构造一个临时路径：不存在 / 语法错误两种情况
    cfg_path = tmp_path / ("missing.yaml" if missing else "bad.yaml")

    if not missing:
        # 写入明显非法的 YAML 内容（缺失右中括号），确保触发 yaml.YAMLError
        cfg_path.write_text("a: [1, 2", encoding="utf-8")

    # Patch 源头：src.core.config.get_config_path
    monkeypatch.setattr(
        "src.core.config.get_config_path",
        lambda name: cfg_path,
    )

    # 确保后续 import 使用的是当前 monkeypatch 后的配置路径，
    # 具体的 sys.modules 管理在下方统一处理。

    # 根据缺失/语法错误，期望不同的异常类型
    # 使用重新 import 的方式触发顶层加载逻辑，避免对 reload 语义过度耦合。
    sys.modules.pop("src.evidence.risk", None)

    if missing:
        with pytest.raises(RuntimeError) as exc_info:
            importlib.import_module("src.evidence.risk")
        msg = str(exc_info.value)
        assert "Failed to load risk rules configuration" in msg
        # 仅依赖文件名，避免对完整路径格式过度耦合
        assert cfg_path.name in msg
    else:
        with pytest.raises(ValueError) as exc_info:
            importlib.import_module("src.evidence.risk")
        msg = str(exc_info.value)
        assert "Invalid YAML in risk_rules.yaml" in msg
        assert "risk_rules.yaml" in msg

    # 恢复 risk 模块留给后续正常 import，避免在仍处于 monkeypatch 环境下重复触发错误。
