---
name: attach-end-effector
description: Mount an end-effector (parallel-jaw gripper, dexterous hand, suction tool, etc.) on a robot arm by attaching its MJCF to the arm's `attachment_site` via MuJoCo's MjSpec API. Use when combining an arm MJCF and an end-effector MJCF into a single combined model (e.g. piper_arm + barrett -> piper_arm_barrett). Handles known gotchas the underlying script doesn't: same-named mesh files silently overwriting each other, end-effectors whose root body origin sits on the wrong face for wrist mounting, empty-prefix failures (entity-name collisions and bare nested `<default>` blocks), and the script silently skipping gripper meshes when the gripper's `<compiler meshdir>` isn't `assets/`.
---

# attach-end-effector

Wrap `attach_arm_gripper.py` (despite the file name, it works for any
end-effector — gripper, dex hand, suction, sensor mount). The script
loads two MJCFs as `MjSpec`, attaches the end-effector at the arm's
`<site name="attachment_site"/>` with a name prefix, compiles, and
writes a combined `<output>.xml` + `<output>.mjb` + `scene.xml` +
`README.md` under `robots/<output>/`.

The script gets the kinematic attach right but does **not** handle:

1. Mesh-filename collisions between arm and end-effector mesh dirs
   (e.g. piper and allegro both ship `base_link.stl` — the second copy
   is silently dropped, mesh refs resolve to the wrong geometry).
2. End-effectors whose root body's origin is on the wrong face of the
   palm for wrist mounting (menagerie hands place the origin at the
   front face, so the body extends *into* the arm under identity quat).
3. Empty-prefix failures: entity-name collisions (`repeated name 'X'`)
   AND bare nested `<default>` blocks in the eef source (`empty class
   name`). Internal namespacing only protects against the first.
4. End-effectors whose `<compiler meshdir>` isn't `assets/` — the
   script hard-codes the gripper mesh source, silently copies zero
   meshes, and emits no warning. Compile fails on missing mesh files.

These are addressed in `references/gotchas.md` and the post-script
checklist in `references/workflow.md`.

## When to use this skill

- Combining any arm + end-effector pair where both ship a standalone
  MJCF and the arm exposes `<site name="attachment_site"/>` at its
  wrist flange.
- The output goes into `robots/<arm>_<eef>/` as a combined model
  consumed by `mjcf_file:` in `robot.json`.

## When NOT to use this skill

- The arm has no `attachment_site` site (add one first, in arm-only).
- You want a URDF combined model (this skill is MJCF-only).
- You want to attach two arms (no `attachment_site` convention there).

## Workflow

1. Verify the arm MJCF has `<site name="attachment_site" .../>` on the
   wrist link. If not, add it first in the arm-only file.
2. **Choose a prefix.** Default to a non-empty prefix
   (e.g. `barrett_`, `right_`). Empty prefix has two failure modes —
   entity-name collisions AND bare nested `<default>` blocks — and
   internal namespacing (e.g. barrett's `bh_*`) only protects against
   the first. See `references/gotchas.md` §3 for the two `grep` checks
   that justify empty if you really want it.
3. Run the script (see Commands).
4. **Verify gripper meshes were actually copied.** The script
   hard-codes `<eef>/assets/` as the source; if the gripper's
   `<compiler meshdir>` is anything else (e.g. barrett uses `meshes`),
   zero gripper meshes get copied and the script emits no warning.
   See `references/gotchas.md` §4 for the parse-meshdir + `cp` recipe.
5. **Check for mesh-filename collisions in the merged `assets/`.** See
   `references/gotchas.md` §1 (silent failure mode that bit us with
   allegro_right + piper — both ship `base_link.stl`).
6. **Check the end-effector mounts flush at the flange.** Open the
   combined `scene.xml` in MuJoCo viewer. If the eef body extends
   *into* the arm, set `pos="0 0 H"` on the prefixed root body so its
   back face sits at the wrist; see `references/gotchas.md` §2.
7. Verify all combined actuators map to the intended joints (sliders
   in viewer should move the right things on both arm and eef).
8. Drop a `robot.json` for the combined folder (mjcf-only registration,
   `urdf_file: null`, `meshes_dir: assets`).

## Commands

Run from the bundle root with the bundle-local venv. The wrapped
script lives in the parent repo at `../attach_arm_gripper.py`.
`attach_arm_gripper.py` resolves relative `--arm` / `--gripper` /
`--output` paths against *its own* directory (the parent repo), not
the bundle's `robots/` — so pass **absolute** paths via `$(pwd)/`.

```bash
cd robot-assets-skills/
./.venv/bin/python ../attach_arm_gripper.py \
    --arm     "$(pwd)/robots/<arm>/<arm>.xml" \
    --gripper "$(pwd)/robots/<eef>/<eef>.xml" \
    --output  "$(pwd)/robots/<arm>_<eef>" \
    --prefix  "<prefix>_" \
    --no-viewer
```

Verify the model compiles and loads:

```bash
./.venv/bin/python -c "
import mujoco
m = mujoco.MjModel.from_xml_path('robots/<arm>_<eef>/<arm>_<eef>.xml')
print('nq=', m.nq, 'nu=', m.nu, 'nbody=', m.nbody)
"
```

View interactively (`DISPLAY=:5` on our headless box):

```bash
DISPLAY=:5 ./.venv/bin/python -m mujoco.viewer \
    --mjcf robots/<arm>_<eef>/scene.xml
```

If `.venv/` doesn't exist or is missing packages, bootstrap per
`AGENTS.md`'s "Python environment" section. If `robots/` is empty,
bootstrap per `README.md`'s "First-time setup" (copy your arm + eef
folders in).

## References

- Step-by-step procedure: `references/workflow.md`
- Known gotchas with concrete fixes: `references/gotchas.md`
