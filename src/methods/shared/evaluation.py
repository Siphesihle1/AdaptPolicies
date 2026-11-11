import os
from typing import Any, Dict, Set, List
from virtual_home.graph_query import N

def get_object_relations(state: Dict[str, Any]) -> Set[str]:
    obj_ids = dict(N(state).select("id", "class_name"))

    return set(
        [
            " ".join([obj_ids[e["from_id"]], e["relation_type"], obj_ids[e["to_id"]]])
            for e in state["edges"]
        ]
    )


def get_object_states(state: Dict[str, Any]) -> Set[str]:
    return set(
        [n["class_name"] + " " + st for n in state["nodes"] for st in n["states"]]
    )


class EvaluationMixin:
    def eval(self):
        ## the evaluation criteria is not perfect
        ## since sometimes the tasks are underspecified, like which object to interact with
        ## for example "turn off lightswitch" could happen in multiple locations
        ## the evaluation happens w.r.t one possible valid state
        ## that the annotator provides

        sr: List[float] = []
        unchanged_conds: List[int] = []
        total_unchanged_conds: List[int] = []
        test_tasks = list(self.plans)

        for g, g_in, task in zip(
            self.final_states, self.initial_states, self.exec_per_task
        ):
            ground_truth_graph = self.ground_truth_graphs[task]

            relations_in = get_object_relations(g_in)
            obj_states_in = get_object_states(g_in)

            relations = get_object_relations(g)
            obj_states = get_object_states(g)

            relations_gt = get_object_relations(ground_truth_graph)
            obj_states_gt = get_object_states(ground_truth_graph)

            changed_gt_relations = relations_gt - relations_in
            changed_gt_obj_states = obj_states_gt - obj_states_in
            changed_relations = relations - relations_in
            changed_obj_states = obj_states - obj_states_in

            unsatisfied_relations = changed_gt_relations - changed_relations
            unsatisfied_obj_states = changed_gt_obj_states - changed_obj_states

            task_log_file = f"{os.getenv('JOB_OUTPUT_DIR')}/task_logs/{'_'.join(task.split(' '))}/task_logs.txt"

            with open(task_log_file, "a") as f:
                f.write(
                    f"\nchanged ground truth relations: {changed_gt_relations}, changed ground truth states: {changed_gt_obj_states}"
                )
                f.write(
                    f"\nchanged relations: {changed_relations}, changed object states: {changed_obj_states}"
                )
                f.write(
                    f"\nunsatisfied state conditions: relations: {unsatisfied_relations}, object states: {unsatisfied_obj_states}"
                )

            unsatisf_conds = len(unsatisfied_relations) + len(unsatisfied_obj_states)
            total_goal_conds = len(changed_gt_relations) + len(changed_gt_obj_states)

            sr.append(
                1 - unsatisf_conds / total_goal_conds if total_goal_conds > 0 else 0
            )

            unchanged_conds.append(
                len(relations_gt.intersection(relations_in) - relations)
                + len(obj_states_gt.intersection(obj_states_in) - obj_states)
            )
            total_unchanged_conds.append(
                len(relations_gt.intersection(relations_in))
                + len(obj_states_gt.intersection(obj_states_in))
            )

            self.results[task] = {
                "PSR": sr[-1],
                "SR": sr[-1:].count(1.0),
                "Precision": (
                    1 - unchanged_conds[-1] / total_unchanged_conds[-1]
                    if total_unchanged_conds[-1] > 0
                    else 0
                ),
                "Exec": self.exec_per_task[task],
            }
            self.task_record(task)["status"] = "evaluated"

        if len(test_tasks) > 0:
            self.results["overall"] = {
                "PSR": sum(sr) / len(sr) if sr else 0,
                "SR": sr.count(1.0) / len(sr) if sr else 0,
                "Precision": (
                    1 - sum(unchanged_conds) / sum(total_unchanged_conds)
                    if sum(total_unchanged_conds) > 0
                    else 0
                ),
                "Exec": (
                    sum(self.exec_per_task.values()) / len(self.exec_per_task)
                    if self.exec_per_task
                    else 0
                ),
            }
