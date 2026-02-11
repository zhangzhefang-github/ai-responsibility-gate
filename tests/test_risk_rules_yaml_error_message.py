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
        # 写入非法 YAML 内容，触发 yaml.YAMLError
        cfg_path.write_text("::not_yaml::", encoding="utf-8")

    # Patch 源头：src.core.config.get_config_path
    monkeypatch.setattr(
        "src.core.config.get_config_path",
        lambda name: cfg_path,
    )

    # 确保 reload 不受 sys.modules 缓存影响
    sys.modules.pop("src.evidence.risk", None)
    import src.evidence.risk as risk_module

    # 根据缺失/语法错误，期望不同的异常类型
    if missing:
        with pytest.raises(RuntimeError) as exc_info:
            importlib.reload(risk_module)
    else:
        with pytest.raises(ValueError) as exc_info:
            importlib.reload(risk_module)

    msg = str(exc_info.value)
    # 错误信息中必须包含最终路径
    assert str(cfg_path) in msg

    # 恢复 risk 模块为正常配置，避免影响后续测试
    sys.modules.pop("src.evidence.risk", None)
    importlib.import_module("src.evidence.risk")

