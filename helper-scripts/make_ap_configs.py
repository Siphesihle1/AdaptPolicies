"""Derive the Adaptive Policies sweep configs from the CaP sweep configs.

For each config/cap-<tag>-<temp>-m<tokens>-<reasoning>.yaml and each placement,
write config/ap-<placement>-<tag>-<temp>-m<tokens>-<reasoning>.yaml with:
- the same provider, model, request timeout and Weave setting;
- ap_* profiles with the CaP condition's settings (ap_recover uses the helper
  settings and ap_replan the policy settings, so every request in a condition
  shares its temperature, reasoning and token budget);
- the adaptive section: CaP's runtime limits, 64 model requests instead of 32
  (D9), a task deadline 1.5 times CaP's to allow for recovery generation, the
  placement and two recoveries per checkpoint.

Run from the repository root: python helper-scripts/make_ap_configs.py
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1] / "config"
PLACEMENTS = ("both", "explicit", "implicit")
PROFILE_SOURCE = {"ap_policy": "cap_policy", "ap_function": "cap_function", "ap_objects": "cap_objects",
                  "ap_question": "cap_question", "ap_recover": "cap_function", "ap_replan": "cap_policy"}
HEADER = """# Adaptive Policies sweep, derived from {source} by helper-scripts/make_ap_configs.py.
# Every LMP, including recovery and replanning, uses the condition's temperature,
# reasoning and token budget. Runtime limits match CaP's except the model-request
# budget (64, since recoveries need model calls) and the task deadline (1.5x CaP's,
# covering all generation, recovery and execution for one task).
"""


def scalar(value):
    return yaml.safe_dump(value, default_flow_style=True).strip().removesuffix("\n...").strip()


def render(source_name, config, placement):
    llm = config["llm"]
    provider = llm["provider"]
    settings = llm["providers"][provider]
    profiles = settings["models"][llm["model"]]
    lines = [HEADER.format(source=source_name).rstrip("\n"), "llm:", f"  provider: {provider}",
             f"  model: {llm['model']}", "  providers:", f"    {provider}:",
             f"      base_url: {settings['base_url']}", f"      timeout: {settings['timeout']}", "      models:",
             f"        {llm['model']}:"]
    for purpose, origin in PROFILE_SOURCE.items():
        lines.append(f"          {purpose}:")
        lines += [f"            {key}: {scalar(value)}" for key, value in profiles[origin].items()]
    lines += ["weave:", f"  enabled: {scalar(config['weave']['enabled'])}", "adaptive:",
              f"  placement: {placement}"]
    cap = dict(config["cap"])
    cap["task_seconds"] = int(cap["task_seconds"] * 1.5)
    cap["max_model_requests"] = 64
    lines += [f"  {key}: {value}" for key, value in cap.items()]
    lines.append("  max_recoveries_per_checkpoint: 2")
    return "\n".join(lines) + "\n"


def main():
    written = 0
    for path in sorted(ROOT.glob("cap-*.yaml")):
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        for placement in PLACEMENTS:
            target = ROOT / f"ap-{placement}-{path.name.removeprefix('cap-')}"
            target.write_text(render(path.name, config, placement), encoding="utf-8", newline="\n")
            written += 1
    print(f"Wrote {written} configs")


if __name__ == "__main__":
    main()
