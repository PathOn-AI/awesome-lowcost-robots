---
name: attach-end-effector
description: Mount an end-effector (parallel-jaw gripper, dexterous hand, suction tool, etc.) on a robot arm by attaching its MJCF to the arm's `attachment_site` via MuJoCo's MjSpec API. Use when combining an arm MJCF and an end-effector MJCF into a single combined model. Handles known gotchas the underlying script doesn't: mesh collisions, wrong mount poses, empty-prefix failures, skipped meshes, and tendon-driven hands.
---

# attach-end-effector

Wrap `attach_arm_end_effector.py`. The script loads two MJCFs as
`MjSpec`, attaches the end-effector at the arm's
`<site name="attachment_site"/>` with a name prefix, compiles, and
writes a combined `<output>.xml` + `<output>.mjb` + `scene.xml` +
`README.md` under `robots/<output>/`.

The script gets the kinematic attach right but does **not** handle:

1. Mesh-filename collisions between arm and end-effector mesh dirs —
   when both ship a same-named STL/OBJ (e.g. `base_link.stl`), the
   second copy is silently dropped and mesh refs resolve to the wrong
   geometry.
2. End-effector mounts at the wrong pos / orientation: the standalone
   palm quat composes with the arm's `attachment_site` quat in
   unpredictable ways, the palm's origin may sit on the front face of
   the palm (Allegro), and the script's natural `pos` is in wrist body
   frame (not site frame), so a naive offset translates the palm in
   the wrong direction when the site has a non-identity quat. Use
   `compute_wrist_mount.py` (preflight) to get the right pos+quat.
3. Empty-prefix failures: entity-name collisions (`repeated name 'X'`)
   AND bare nested `<default>` blocks in the eef source (`empty class
   name`). Internal namespacing only protects against the first.
4. End-effectors whose `<compiler meshdir>` isn't `assets/` — the
   script hard-codes the eef mesh source, silently copies zero
   meshes, and emits no warning. Compile fails on missing mesh files.
5. Tendon-driven hands — `MjSpec.attach` can drop most tendon
   actuators/sensors when the eef exposes controls as
   `<position tendon="...">`.

These are addressed in `references/gotchas.md` and the post-script
checklist in `references/workflow.md`.

## When to use this skill

- Combining any arm + end-effector pair where both ship a standalone
  MJCF and the arm exposes `<site name="attachment_site"/>` at its
  wrist flange.
- The output goes into `robots/<arm>_<eef>/` as a combined MJCF model
  (with merged `assets/`).

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
3. **Preflight: compute the mount pos + quat** with the bundled
   helper. Pass BOTH the arm and the eef so it reads the
   `attachment_site` quat and outputs values in wrist body frame:
   ```bash
   ./.venv/bin/python .claude/skills/attach-end-effector/scripts/compute_wrist_mount.py \
       robots/<eef>/<eef>.xml --arm robots/<arm>/<arm>.xml
   ```
   It prints a single `pos="X Y Z" quat="W X Y Z"` line to apply on
   the prefixed root body after the script runs (step 7 below). If
   the palm visually mounts rotated, re-run with `--twist 90/180/270`
   and pick the one that looks right. See `references/gotchas.md` §2.
4. Run the script (see Commands).
5. **Verify end-effector meshes were actually copied.** The script
   hard-codes `<eef>/assets/` as the source; if the end-effector's
   `<compiler meshdir>` is anything else (e.g. `meshes`, unset, etc.),
   zero eef meshes get copied and the script emits no warning.
   See `references/gotchas.md` §4 for the parse-meshdir + `cp` recipe.
6. **Check for mesh-filename collisions in the merged `assets/`.** See
   `references/gotchas.md` §1 — same-named STL/OBJ files between arm
   and eef silently overwrite each other.
7. **Apply the helper's pos + quat** to the prefixed root body in the
   combined XML. Both must be applied together — using one without the
   other reproduces the original problem; see `references/gotchas.md` §2.
8. Open the combined `scene.xml` in `mujoco.viewer` and verify the
   palm mounts flush at the flange with no finger/wrist clipping. If
   the orientation is off, dial in `--twist` (step 3) and re-apply.
9. Verify all combined actuators/tendons/sensors survived. Expected
   `nu` is usually `arm.nu + eef.nu`; tendon-driven hands can also
   require `ntendon` and `<sensor>` checks. See `references/gotchas.md`
   §5 for Aero-style tendon hands.
10. Verify all combined actuators map to the intended joints or
   tendons (sliders in viewer should move the right things on both arm
   and eef).

## Commands

Run from the bundle root with the bundle-local venv. The wrapped
script ships in this skill at
`.claude/skills/attach-end-effector/scripts/attach_arm_end_effector.py`.
The script resolves relative `--arm` / `--end-effector` / `--output`
paths against *its own* directory, so pass **absolute** paths via
`$(pwd)/` to land outputs under the bundle's `robots/`.

```bash
cd robot-assets-skills/
./.venv/bin/python .claude/skills/attach-end-effector/scripts/attach_arm_end_effector.py \
    --arm          "$(pwd)/robots/<arm>/<arm>.xml" \
    --end-effector "$(pwd)/robots/<eef>/<eef>.xml" \
    --output       "$(pwd)/robots/<arm>_<eef>" \
    --prefix       "<prefix>_" \
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

View interactively (set `$DISPLAY` first if headless — see `AGENTS.md`):

```bash
./.venv/bin/python -m mujoco.viewer \
    --mjcf robots/<arm>_<eef>/scene.xml
```

If `.venv/` doesn't exist or is missing packages, bootstrap per
`AGENTS.md`'s "Python environment" section. If `robots/` is empty,
bootstrap per `README.md`'s "First-time setup" (copy your arm + eef
folders in).

## References

- Step-by-step procedure: `references/workflow.md`
- Known gotchas with concrete fixes: `references/gotchas.md`
