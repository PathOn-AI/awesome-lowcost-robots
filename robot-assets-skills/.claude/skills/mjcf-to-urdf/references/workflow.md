# `mjcf-to-urdf` Workflow

Step-by-step procedure for converting MJCF to URDF for a downstream
URDF-only consumer.

## Preflight

1. **Confirm the consumer can't take MJCF directly.** Skip this skill
   for any consumer that supports MJCF natively (MuJoCo, mink, MJX,
   IsaacSim, mujoco-python-viewer, etc.). The conversion is lossy;
   skipping it is always preferable.

2. **Check upstream for a hand-maintained URDF first.** Most robots
   that have an MJCF also have a URDF (often what the MJCF was
   originally built from). A hand-maintained URDF is always better
   than auto-converting.

   ```bash
   # If the MJCF came from mujoco_menagerie, the source URDF is
   # often in the same upstream package or a manufacturer repo.
   grep -i 'urdf\|source\|original' robots/<robot>/<robot>.xml
   grep -i 'urdf\|source\|original' robots/<robot>/README.md  2>/dev/null
   ```

3. **Inventory what will be lost.** Note these counts before
   conversion — they tell you what the consumer needs to handle:

   ```bash
   ./.venv/bin/python -c "
   import mujoco
   m = mujoco.MjModel.from_xml_path('robots/<robot>/<robot>.xml')
   print('equality:', m.neq)
   print('actuators:', m.nu)
   print('keyframes:', m.nkey)
   "
   grep -c '<exclude' robots/<robot>/<robot>.xml
   ```

   Each of these gets dropped — if any are non-zero, see the
   per-loss workarounds in `gotchas.md`.

## Convert

From the bundle root, with the bundle-local venv:

```bash
cd robot-assets-skills/
./.venv/bin/python ../convert_mjcf_urdf.py \
    "$(pwd)/robots/<robot>/<robot>.xml" --to-urdf
```

Output goes to `robots/<robot>/<robot>.urdf` by default.

Verify it parses:

```bash
./.venv/bin/python -c "
import mujoco
m = mujoco.MjModel.from_xml_path('robots/<robot>/<robot>.urdf')
print('parsed: nq=', m.nq, 'nbody=', m.nbody)
"
```

`nu = 0` is **expected** — URDF has no actuators (gotcha §2).

## Post-convert fixes

### Fix 1: Mesh paths

Inspect the URDF's mesh refs:

```bash
grep 'filename=' robots/<robot>/<robot>.urdf | sort -u | head
```

If they use `package://` (ROS-only) or `file://` (absolute), rewrite to
URDF-relative paths so the URDF works outside ROS:

```bash
sed -i 's|filename="package://[^/]*/|filename="|g' robots/<robot>/<robot>.urdf
sed -i 's|filename="file:///[^"]*meshes/|filename="meshes/|g' robots/<robot>/<robot>.urdf
```

Test in your target consumer (RViz if visualizing, pinocchio if doing
FK/IK).

### Fix 2: Re-add `<mimic>` for any dropped equality constraints

If the preflight showed `equality > 0`, those joint couplings were
lost. Hand-edit the URDF to add `<mimic>` clauses where the consumer
needs them (URDF has `<mimic>` for the simple linear case — but no
analog for polynomial polycoefs). See `gotchas.md` §1.

### Fix 3: Document losses in URDF leading comment

Add a comment at the top of the converted URDF so future readers
know what's missing:

```xml
<?xml version="1.0"?>
<!--
This URDF was auto-converted from <robot>.xml (MJCF source).
Lost in conversion:
- <equality> constraints (N coupled joints became independent)
- <actuator> block (re-tune controller separately)
- <contact><exclude> entries (re-derive in SRDF if using MoveIt)
- <keyframe> block (M named poses; document elsewhere)

Use only for kinematic tasks (visualization, FK, IK). Do NOT use
for dynamics simulation; results will be wrong. Re-export from
MJCF source if needed.
-->
<robot name="<robot>">
...
```

## Verify

1. **Open in the target consumer** (RViz, pinocchio script, MoveIt
   setup assistant, etc.). The conversion is for that specific
   consumer; verify there.

2. **For RViz:** check all meshes load and joints can be commanded
   from the joint-state publisher GUI.

3. **For pinocchio:** confirm FK matches MJCF FK at the same joint
   values:

   ```python
   import mujoco, pinocchio as pin, numpy as np

   mj_m = mujoco.MjModel.from_xml_path('robots/<robot>/<robot>.xml')
   mj_d = mujoco.MjData(mj_m)
   pin_m = pin.buildModelFromUrdf('robots/<robot>/<robot>.urdf')
   pin_d = pin_m.createData()

   q = np.zeros(mj_m.nq)  # or some test pose
   mj_d.qpos[:] = q
   mujoco.mj_forward(mj_m, mj_d)

   pin.forwardKinematics(pin_m, pin_d, q)

   # Compare end-effector / wrist site positions; expect close match
   # (small differences from slightly different inertia/origin frames are OK)
   ```

   FK mismatches mean either mesh-frame discrepancies or dropped
   `<equality>` (the simulated joints are different).

## Register (rarely)

URDFs auto-converted from MJCF typically aren't registered upstream
as the canonical URDF — they're derived artifacts for one consumer.
If you do register one, document the conversion in the changelog:

```json
{
  "version": {
    "version": "1.0.0-derived",
    "is_stable": false,
    "urdf_file": "<robot>.urdf",
    "changelog": "Auto-converted from <robot>.xml (MJCF) via mjcf-to-urdf skill. LOSSY — see leading comment in URDF for details. For kinematic use only."
  }
}
```

`is_stable: false` is intentional; consumers should know this URDF is
derived.
