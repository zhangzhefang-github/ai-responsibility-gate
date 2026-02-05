import yaml
from ..core.models import Evidence, GateContext
from ..core.config import get_config_path

with open(get_config_path("kb_meta.yaml"), encoding="utf-8") as f:
    KB_META = yaml.safe_load(f)

async def collect(ctx: GateContext) -> Evidence:
    return Evidence(
        provider="knowledge",
        available=True,
        data={
            "kb_version": KB_META["version"],
            "expired": KB_META["expired"],
            "kb_id": KB_META["kb_id"]
        }
    )
