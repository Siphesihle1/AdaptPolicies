"""Exercise the pinned scene-0 door with real native responses and leaf poses."""

import argparse
import json
import math
import os
import time
from pathlib import Path

from simulation.unity_simulator.comm_unity import UnityCommunication
from virtual_home.environment import unity_execution_succeeded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cycles", required=True, type=int)
    parser.add_argument(
        "--animation",
        required=True,
        choices=("fast", "animated"),
        help="Close interaction mode; setup actions use fast execution.",
    )
    args = parser.parse_args()
    if args.cycles < 1:
        parser.error("--cycles must be positive")
    args.output.mkdir(parents=True, exist_ok=False)
    comm = UnityCommunication(port=args.port, timeout_wait=90)
    records = []

    def graph():
        ok, value = comm.environment_graph()
        assert ok
        return value

    def node(value, identifier):
        return next(n for n in value["nodes"] if n["id"] == identifier)

    def angle(value):
        rotation = node(value, 224)["obj_transform"]["rotation"]
        norm = math.sqrt(sum(v * v for v in rotation))
        return math.degrees(2 * math.acos(min(1, abs(rotation[3]) / norm)))

    def run(action, expected=True, animated=False):
        response = comm.render_script(
            ["<char0> " + action],
            recording=False,
            skip_animation=not animated,
            find_solution=False,
        )
        success = unity_execution_succeeded(response)
        records.append({"action": action, "success": success, "response": response})
        (args.output / "trace.json").write_text(json.dumps(records, indent=2))
        print(success, action, response if success != expected else "", flush=True)
        assert success == expected, response

    results = []
    for cycle in range(args.cycles):
        for carry in (False, True):
            assert comm.reset(0)
            assert comm.add_character("Chars/Male2", initial_room="kitchen")
            initial = graph()
            assert angle(initial) > 120
            run("[walk] <kitchen> (205)")
            if carry:
                run("[find] <garbagecan> (229)")
                run("[grab] <garbagecan> (229)")
            run("[walk] <door> (224)")
            run("[close] <door> (224)", animated=args.animation == "animated")
            final = graph()
            assert "CLOSED" in node(final, 224)["states"]
            assert angle(final) < 5, angle(final)
            before = node(initial, 224)["obj_transform"]["position"]
            after = node(final, 224)["obj_transform"]["position"]
            assert math.dist(before, after) < 0.03
            if carry:
                assert any(
                    edge["from_id"] == 1
                    and edge["to_id"] == 229
                    and edge["relation_type"] in {"HOLDS_RH", "HOLDS_LH"}
                    for edge in final["edges"]
                )
                diagnostics = os.environ.get("ADAPTPOLICIES_NATIVE_DIAGNOSTICS")
                if diagnostics:
                    snapshots = Path(diagnostics).glob("snapshot-*.json")
                    latest = max(snapshots, key=lambda p: int(p.stem.split("-")[-1]))
                    live = json.loads(latest.read_text())
                    bin_item = next(n for n in live["items"] if n["id"] == 229)
                    door_item = next(n for n in live["items"] if n["id"] == 224)
                    assert "Hand/Garbage_can_8" in bin_item["hierarchy"]
                    assert door_item["isKinematic"]
            time.sleep(0.2)
            assert abs(angle(graph()) - angle(final)) < 0.1
            (args.output / f"cycle-{cycle}-carry-{carry}.json").write_text(
                json.dumps(final, indent=2)
            )
            results.append(
                {"cycle": cycle, "carry": carry, "closed_angle": angle(final)}
            )

    assert comm.reset(0)
    assert comm.add_character("Chars/Male2", initial_room="kitchen")
    for action in (
        "[find] <apple> (438)",
        "[grab] <apple> (438)",
        "[find] <garbagecan> (229)",
        "[grab] <garbagecan> (229)",
        "[walk] <door> (224)",
    ):
        run(action)
    run("[close] <door> (224)", expected=False)
    blocked = graph()
    assert "OPEN" in node(blocked, 224)["states"] and angle(blocked) > 120
    assert (
        len(
            [
                e
                for e in blocked["edges"]
                if e["from_id"] == 1 and e["relation_type"].startswith("HOLDS")
            ]
        )
        == 2
    )
    (args.output / "result.json").write_text(
        json.dumps(
            {
                "cycles": results,
                "full_hands_rejected": True,
                "animation": args.animation,
            },
            indent=2,
        )
    )
    print("Door closure pose and free-hand controls passed.", flush=True)


if __name__ == "__main__":
    main()
