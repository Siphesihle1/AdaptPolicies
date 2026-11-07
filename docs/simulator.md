# Simulator changes

AdaptPolicies uses a custom build of the official VirtualHome Linux v2.3.0 player.
The original fixed scenes, object identities, meshes and legacy hand IK are
retained. The simulator build sources are maintained outside this repository.
All changes below are included in the compiled build and require no activation
variable. Select the installed player directory with `VIRTUALHOME_SIM_ROOT`.

## Included behavior

| Area | Behavior |
| --- | --- |
| Hanging garments | Mesh-only hanging shirts use the existing horizontal native grab pose. Original hand attachment, placement and instance selection remain. |
| Curtains | Native Open/Close gathers and restores the original window-curtain panels. Shower curtains retain their existing interactions. |
| Windows | The original window mesh is partitioned into frame and hinged sash while preserving its triangles, glass and materials. |
| Lidless bins | Unsupported Open/Close actions are unnecessary. Collider handling permits native insertion into the original open bin. |
| Empty-bin carrying | The known small empty scene-0 bin can be carried to the kitchen doorway. Filled bins, unsupported prefabs and full hands reject pickup. |
| Binders | The existing folder receives native opening transitions and a usable paper compartment. Paper placement checks opening state, held state and geometric fit. |
| Sink placement | Native release poses fit the original frying pan and washing objects onto the sink without resizing them. |
| Washing machines | An articulated door, drum and power indicator are derived from the existing housing. Native insertion checks door state and payload dimensions; powered drum motion stops when switched off. |
| Rugs | Fold/Unfold changes the held rug's geometry so it can fit the washer and later return to its original shape. |
| Tool manipulation | Apply and Use execute supported toothpaste/brush preparation and brushing motions using the existing character rig. |
| Door interactions | The kitchen door opens and closes through its original hand interactions and torque. Closing uses temporary hinge limits; fixed-housing collision handling allows both directions. The body latches only after physical closure. Individual and batched graph observations reflect completed physical results. |
| Static orientation | Initial static FACING is recomputed with actor-body occlusion excluded, retaining the original visibility and angle rules. |

Opening interactions wait for their native transitions to finish, including fast
execution. The kitchen doorway retains its fixed native midpoint and kitchen-side
approach for both Open and Close. Door collision exclusions and hinge settings restore after the interaction;
existing actor and payload collision rules remain. No successful execution
response is fabricated by these changes. Kitchen-door Open runs its original
animation at normal speed even for fast requests, preserving the hand-contact
torque window. Its housing and stopper contacts are temporarily excluded while
opening, then restored. A measured open pose is required before completion is
recorded; other scene doors retain their native behavior.

## Planning actions and states

| Action | Supported behavior and requirements |
| --- | --- |
| `fold(rug)` / `unfold(rug)` | Requires a held supported rug and a free second hand. Updates its geometry and FOLDED/UNFOLDED state. |
| `apply(toothpaste, toothbrush)` | Requires both objects to be held and the tube cap to be open. Moves the nozzle to the bristles and deposits visible paste, deriving APPLIED. |
| `use(toothbrush)` | Requires a held prepared brush. Performs the calibrated brushing motion, consumes the paste and derives USED. |
| `talk(cellphone)` | Uses the existing native Talk action on a held phone. Confirmed use derives USED; it does not toggle phone power. |
| `read(book)` | Uses the supported native Read interaction on the selected held book. |

Apply and Use are general action names; the current implementation supports only
the documented toothpaste/brush pair. Other tool pairs reject explicitly. No
toothbrushing-specific command is added.

The AdaptPolicies runtime derives WASHED, HEATED and selected USED effects from
confirmed execution and observed relations. These are evaluation augmentations;
they are not all native Unity states. Closet interiors remain accessible while
their assets report CLOSED, matching native pickup and placement behavior.
Closed fridges, cabinets and washers retain their access checks. Character-room
observations follow the character's actual position after movement.

## Evaluation impact and limitations

Report the simulator build and dataset revision with results. Added actions,
physical affordances, derived states and revised reference goals change the
evaluation setting; compare systems using the same versions. Successful stored
annotations do not establish that generated plans or every same-class instance
will succeed. See [dataset validation](dataset_validation.md) and
[ground-truth evaluation](ground_truth_graphs.md).

Rug folding is deterministic mesh deformation, and floor drying is an explicit
proxy. Toothbrush contact is calibrated for Male2. Washing and heating effects
use the documented runtime rules rather than a fluid or thermal simulation.
The supported kitchen door passes repeated fast and animated Close/Open cycles,
including carrying the bin and batches ending in either state. These controls
cover that pinned door and approach, rather than every door/character configuration.
The trash annotation ends at carrying the bin to the doorway and does not require
Close or reopening.
