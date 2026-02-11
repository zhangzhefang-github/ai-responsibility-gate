from pathlib import Path

import yaml

from examples.pr_gate_ai_review_loop.signal_validation import load_signal_allowlist


def test_signals_catalog_loadable_and_well_formed():
    """
    signals_catalog.yaml 必须可加载，且每个 signal 至少包含：
    - name
    - description
    - default_risk_floor
    且 name 唯一。
    """
    catalog_path = Path("examples/pr_gate_ai_review_loop/signals_catalog.yaml")
    assert catalog_path.exists(), "signals_catalog.yaml must exist"

    with open(catalog_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "version" in data
    signals = data.get("signals")
    assert isinstance(signals, list) and signals, "signals list must be non-empty"

    names = set()
    for item in signals:
        assert isinstance(item, dict)
        name = item.get("name")
        desc = item.get("description")
        floor = item.get("default_risk_floor")

        assert name, "signal.name is required"
        assert desc, f"signal '{name}' must have description"
        assert floor in {"R0", "R1", "R2", "R3"}, f"signal '{name}' must have valid default_risk_floor"

        assert name not in names, f"duplicate signal name: {name}"
        names.add(name)

    # load_signal_allowlist 应与 YAML 中的 name 集合一致或子集（允许未来过滤）
    allowlist = load_signal_allowlist()
    assert names.issuperset(allowlist)

