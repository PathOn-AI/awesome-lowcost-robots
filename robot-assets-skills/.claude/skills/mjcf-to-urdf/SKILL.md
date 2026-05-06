---
name: mjcf-to-urdf
description: Convert an MJCF (MuJoCo's XML format) to URDF for downstream consumers that don't speak MJCF (RViz, pinocchio, ROS-based motion planning, etc.). The conversion is lossy — `<equality>` constraints, position actuators, contact excludes, and keyframes are all dropped. Use this skill ONLY when a URDF-only consumer needs the kinematic tree; do not use the converted URDF for dynamics.
---

# mjcf-to-urdf

Wrap `convert_mjcf_urdf.py --to-urdf` (which uses
`mjcf-urdf-simple-converter`). Lower-priority skill in the bundle —
URDF→MJCF is the direction we usually want, since MJCF is more
expressive. The reverse is for downstream tools that don't speak MJCF.

The conversion preserves the kinematic tree (links, joints, parent/child,
visual/collision meshes, joint limits) but **drops** several MJCF-only
features:

1. **`<equality>` constraints disappear.** Any joint coupling expressed
   as `polycoef` (the MJCF equivalent of URDF mimic joints) is lost.
   Joints that should be coupled become independent in the URDF.
2. **Actuators are dropped.** URDF has no actuator concept — joints
   exist, nothing drives them. Downstream consumers must add their own
   joint controllers.
3. **Contact excludes don't survive.** URDF has no contact-exclusion
   element. Anything that was excluded becomes an active collision
   pair in the URDF — usually fine for a *visualization* consumer
   like RViz, but breaks anything doing physics from the URDF.
4. **Keyframes are dropped.** Any rest-pose snapshots in the MJCF are
   discarded.
5. **Position actuators with `kp`/`kv` are dropped.** Any tuning is
   lost; the URDF has no analog.

The output is **for kinematic visualization or planning, not
dynamics**. If the consumer simulates from the URDF, they'll get
wrong results.

## When to use this skill

- A downstream consumer (RViz, pinocchio, MoveIt, IK libraries) needs
  a URDF and the canonical model is MJCF.
- You only need the kinematic tree: forward kinematics, IK, collision
  visualization. You don't need dynamics fidelity.

## When NOT to use this skill

- You need to simulate dynamics from the URDF — converting will look
  fine but produce wrong physics. Re-export from the MJCF source each
  time, or use `urdf-to-mjcf` in reverse only after re-tuning.
- A URDF version of the robot already exists upstream — adopt that
  instead. A hand-maintained URDF is almost always more accurate than
  one auto-converted from MJCF.
- The MJCF uses `<equality>` constraints that the consumer needs (e.g.
  underactuated hand) — the consumer will silently get the wrong
  kinematics. In this case, regenerate the URDF from the *original*
  source (not from the MJCF), or document the lost coupling in the URDF
  comments.

## Workflow

1. **Confirm the consumer actually needs URDF.** Many tools support
   MJCF directly (mink, mujoco-python-viewer, IsaacSim) — skip this
   skill if so.
2. **Check upstream for a hand-maintained URDF.** If one exists, use
   it. Don't auto-convert.
3. Run the converter (see Commands).
4. **Verify mesh paths.** The converter may produce
   `meshdir`-relative paths that don't resolve under URDF's normal
   `package://` or relative-to-URDF conventions. Manually inspect.
5. **Document what was lost** in the URDF's leading comment so future
   readers know they're looking at a partial representation.
6. (Optional) Drop a `robot.json` if registering upstream — but URDF
   from MJCF conversion typically isn't registered as the canonical;
   it's a derived artifact for one consumer.

## Commands

Run from the bundle root with the bundle-local venv. Pass an absolute
input path so the script doesn't try to resolve it relative to the
parent repo:

```bash
cd robot-assets-skills/
./.venv/bin/python ../convert_mjcf_urdf.py \
    "$(pwd)/robots/<robot>/<robot>.xml" --to-urdf
```

By default the output goes to the same directory with `.urdf`
extension. To pick an explicit output path:

```bash
./.venv/bin/python ../convert_mjcf_urdf.py \
    "$(pwd)/robots/<robot>/<robot>.xml" \
    "$(pwd)/robots/<robot>/<robot>.urdf"
```

Verify the URDF parses:

```bash
./.venv/bin/python -c "
import mujoco
m = mujoco.MjModel.from_xml_path('robots/<robot>/<robot>.urdf')
print('nq=', m.nq, 'nu=', m.nu, 'nbody=', m.nbody)
"
```

`nu = 0` is **expected** — URDF has no actuators. Anything in the
source MJCF's `<actuator>` block is gone.

If `.venv/` is missing or broken, bootstrap per `AGENTS.md`'s "Python
environment" section.

## References

- Step-by-step procedure: `references/workflow.md`
- The losses with concrete examples: `references/gotchas.md`
