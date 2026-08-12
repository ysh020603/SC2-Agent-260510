from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import json
import re
import shutil
from pathlib import Path


POLICY_METHOD = "full_executable_normalized_graph_v11"
KNOWLEDGE_METHOD = "full_knowledge_grounded_graph_v13"
OUTPUT_METHOD = "full_knowledge_executable_graph_v14"
OVERLAY_SECTIONS = (
    "Human-Trajectory Interpretation",
    "Applicability Checks",
    "General Failure Mode",
    "Risk Direction",
    "Safer Re-evaluation",
    "Stop / Repair / Recheck",
    "Knowledge-Grounded Execution Envelope",
)


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _node_text(node: dict) -> str:
    return " ".join(
        str(node.get(key) or "") for key in ("title", "trigger_summary", "summary", "phase")
    )


def similarity(left: dict, right: dict) -> float:
    left_text, right_text = _node_text(left), _node_text(right)
    left_tokens, right_tokens = _tokens(left_text), _tokens(right_text)
    union = left_tokens | right_tokens
    jaccard = len(left_tokens & right_tokens) / len(union) if union else 0.0
    sequence = SequenceMatcher(None, left_text.lower(), right_text.lower()).ratio()
    return round(0.7 * jaccard + 0.3 * sequence, 6)


def align_nodes(policy_nodes: dict, knowledge_nodes: dict) -> dict[str, tuple[str, float]]:
    pairs = sorted(
        (
            (similarity(policy, knowledge), policy_id, knowledge_id)
            for policy_id, policy in policy_nodes.items()
            for knowledge_id, knowledge in knowledge_nodes.items()
        ),
        reverse=True,
    )
    mapping: dict[str, tuple[str, float]] = {}
    used_knowledge: set[str] = set()
    for score, policy_id, knowledge_id in pairs:
        if policy_id in mapping or knowledge_id in used_knowledge:
            continue
        mapping[policy_id] = (knowledge_id, score)
        used_knowledge.add(knowledge_id)
    # Skill variants can occasionally have unequal node counts. Reuse the best
    # semantic knowledge node only for an unmatched policy node.
    for policy_id, policy in policy_nodes.items():
        if policy_id in mapping:
            continue
        best = max(
            ((similarity(policy, knowledge), knowledge_id) for knowledge_id, knowledge in knowledge_nodes.items()),
            default=(0.0, ""),
        )
        mapping[policy_id] = (best[1], best[0])
    return mapping


def _section(markdown: str, heading: str) -> str:
    match = re.search(
        rf"(?ms)^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)",
        markdown,
    )
    return match.group(1).strip() if match else ""


def merge_node(policy_markdown: str, knowledge_markdown: str, knowledge_id: str, score: float) -> str:
    blocks = []
    for heading in OVERLAY_SECTIONS:
        body = _section(knowledge_markdown, heading)
        if body:
            blocks.append(f"### {heading}\n\n{body}")
    if not blocks:
        return policy_markdown
    overlay = (
        "## Knowledge Constraint Overlay\n\n"
        f"Semantically aligned validated knowledge node: `{knowledge_id}` (alignment score {score:.3f}). "
        "The executable policy above remains primary; use this overlay only for factual feasibility, "
        "candidate selection, and repair checks.\n\n"
        + "\n\n".join(blocks)
        + "\n\n"
    )
    marker = "## Possible Next Situations"
    if marker in policy_markdown:
        return policy_markdown.replace(marker, overlay + marker, 1)
    return policy_markdown.rstrip() + "\n\n" + overlay


def _negative_markdown(markdown: str, node_id: str) -> str:
    body = markdown.split("## Possible Next Situations", 1)[0].rstrip()
    body = re.sub(r"(?m)^# N[0-9]+\s+—", f"# {node_id} —", body, count=1)
    return body + (
        "\n\n## Routing Boundary\n\n"
        "This is a negative experience branch. Use it only to identify the matched failure mode, "
        "safer re-evaluation, stop condition, and reachable repair. Never reproduce the failed direction.\n"
    )


def build(skill_root: Path, destination_root: Path | None = None) -> dict:
    skill_root = skill_root.resolve()
    destination_root = (destination_root or skill_root).resolve()
    policy_root = skill_root / POLICY_METHOD
    knowledge_root = skill_root / KNOWLEDGE_METHOD
    destination = destination_root / OUTPUT_METHOD
    for required in (policy_root, knowledge_root):
        if not required.is_dir():
            raise FileNotFoundError(required)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite existing method: {destination}")

    rows = []
    for policy_index_path in sorted(policy_root.glob("*/*/*/index.json")):
        relative = policy_index_path.parent.relative_to(policy_root)
        knowledge_dir = knowledge_root / relative
        knowledge_index_path = knowledge_dir / "index.json"
        if not knowledge_index_path.is_file():
            raise FileNotFoundError(knowledge_index_path)
        policy_index = json.loads(policy_index_path.read_text(encoding="utf-8"))
        knowledge_index = json.loads(knowledge_index_path.read_text(encoding="utf-8"))
        mapping = align_nodes(policy_index["nodes"], knowledge_index["nodes"])

        target = destination / relative
        shutil.copytree(policy_index_path.parent, target)
        policy_index["method"] = OUTPUT_METHOD

        negative_routes = []
        negative_nodes = [
            (node_id, node)
            for node_id, node in sorted(knowledge_index["nodes"].items())
            if str(node.get("type") or "").lower() == "negative"
        ]
        for ordinal, (knowledge_id, knowledge_node) in enumerate(negative_nodes, 1):
            routed_from, route_score = max(
                (
                    (policy_id, similarity(policy_node, knowledge_node))
                    for policy_id, policy_node in policy_index["nodes"].items()
                    if not policy_id.startswith("KNEG")
                ),
                key=lambda item: item[1],
            )
            negative_id = f"KNEG{ordinal:03d}"
            negative_path = f"nodes/{negative_id}.md"
            policy_index["nodes"][negative_id] = {
                "children": [],
                "path": negative_path,
                "summary": knowledge_node.get("summary") or "",
                "title": knowledge_node.get("title") or negative_id,
                "trigger_summary": knowledge_node.get("trigger_summary") or "",
                "type": "negative",
            }
            children = policy_index["nodes"][routed_from].setdefault("children", [])
            if negative_id not in children:
                children.append(negative_id)
            source_negative_path = knowledge_dir / knowledge_node["path"]
            (target / negative_path).write_text(
                _negative_markdown(source_negative_path.read_text(encoding="utf-8"), negative_id),
                encoding="utf-8",
            )
            negative_routes.append(
                {
                    "negative_node": negative_id,
                    "knowledge_node": knowledge_id,
                    "routed_from": routed_from,
                    "score": route_score,
                }
            )
        (target / "index.json").write_text(
            json.dumps(policy_index, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
        root_path = target / "SKILL.md"
        root_path.write_text(
            re.sub(r"(?m)^- Method:.*$", "- Method: Knowledge-Constrained Executable Full V14", root_path.read_text(encoding="utf-8")),
            encoding="utf-8",
        )
        alignments = []
        for policy_id, (knowledge_id, score) in sorted(mapping.items()):
            policy_node_path = target / policy_index["nodes"][policy_id]["path"]
            knowledge_node_path = knowledge_dir / knowledge_index["nodes"][knowledge_id]["path"]
            policy_node_path.write_text(
                merge_node(
                    policy_node_path.read_text(encoding="utf-8"),
                    knowledge_node_path.read_text(encoding="utf-8"),
                    knowledge_id,
                    score,
                ),
                encoding="utf-8",
            )
            alignments.append({"policy_node": policy_id, "knowledge_node": knowledge_id, "score": score})
        rows.append(
            {
                "skill_id": policy_index["skill_id"],
                "path": str(relative),
                "alignments": alignments,
                "negative_routes": negative_routes,
            }
        )

    manifest = {
        "schema_version": 1,
        "method": OUTPUT_METHOD,
        "policy_method": POLICY_METHOD,
        "knowledge_method": KNOWLEDGE_METHOD,
        "skills": len(rows),
        "rows": rows,
        "design": "v11 executable policy backbone + semantically aligned validated v13 knowledge overlays",
    }
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "BUILD_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-root", type=Path, required=True)
    parser.add_argument("--destination-root", type=Path)
    args = parser.parse_args()
    manifest = build(args.skill_root, args.destination_root)
    print(json.dumps({"method": manifest["method"], "skills": manifest["skills"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
