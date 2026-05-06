---
name: urdf-to-mjcf
description: Convert a URDF to MJCF (MuJoCo's XML format) and post-tune the result so it actually simulates correctly. MuJoCo's URDF loader silently drops mimic joints, often produces 100x oversized inertias, generates no actuators, and emits no contact excludes — so a raw conversion is rarely usable as-is. Use this skill when bringing a new robot/hand from a URDF source into MuJoCo. Always check mujoco_menagerie first — if a hand-tuned MJCF already exists there, adopt it instead of running the converter.
---

# urdf-to-mjcf

Wrap `convert_mjcf_urdf.py --to-mjcf` (which uses MuJoCo's built-in URDF
loader via `mjcf-urdf-simple-converter`), then post-tune the output
because the auto-conversion is rarely usable as-is.

The script gets the kinematic tree right but does **not** handle:

1. **Mimic joints get silently dropped.** MuJoCo's URDF loader has no
   way to express URDF `<mimic>` semantics. All mimic'd joints become
   independent free joints; the underlying coupling is lost.
2. **Inertias are often 100x oversized.** Stock URDFs from xacro/SDF
   pipelines frequently use placeholder inertia values that produce
   absurd dynamics in MuJoCo (e.g. fingers that won't move at any
   reasonable kp).
3. **No actuators.** The output has joints but nothing drives them.
   No actuator block at all.
4. **No contact excludes.** Adjacent links that touch in the rest pose
   (palm↔first-knuckle pairs are the typical case) get treated as
   active contacts and the joint physically can't reach its
   commanded angle.
5. **No `autolimits`, no `implicitfast` integrator.** Defaults that
   matter for stable dexterous-hand sim aren't set.

**Strong preference: check `mujoco_menagerie` first.** If your robot
or hand already lives in
`https://github.com/google-deepmind/mujoco_menagerie`, adopt that
MJCF verbatim — the MuJoCo team has already tuned it, and re-running
the converter on a URDF will produce a strictly worse result.

These post-tune fixes are documented in `references/gotchas.md` and
the step-by-step is in `references/workflow.md`.

## When to use this skill

- A new robot/hand with a URDF you need to simulate in MuJoCo and no
  upstream MJCF (menagerie or otherwise) exists.
- Your existing URDF is the source of truth (e.g. you maintain it for
  RViz/pinocchio) and you need an MJCF for sim.

## When NOT to use this skill

- An upstream MJCF exists in `mujoco_menagerie` or the manufacturer's
  repo — adopt it instead. Re-tuning is wasted work.
- You only need URDF (e.g. for RViz/pinocchio) — skip MJCF entirely.
- The robot is going to be combined with another via
  `attach-end-effector` and only that combined model needs to
  simulate — convert the components individually first.

## Workflow

1. **Check `mujoco_menagerie` first.** If the robot is there, copy
   its MJCF into `robots/<robot>/<robot>.xml` and stop. Don't run
   the converter.
2. **Verify the URDF loads in MuJoCo standalone.** If MuJoCo can't
   parse it, the converter won't help — fix the URDF first.
3. Run the converter (see Commands).
4. **Post-tune the MJCF.** Walk through the five fix categories in
   `references/gotchas.md`: mimics→`<equality>`, inertias,
   actuators, contact excludes, compiler/option attributes.
5. **Verify in the viewer.** Each actuator slider should drive the
   intended joint(s) to the commanded angle without numerical
   blowup or contact-blocked motion.
6. Drop a `robot.json` (mjcf registration; if URDF + MJCF use
   different mesh dirs, set `urdf_file: null` per ur5e/piper convention).

## Commands

Run from the bundle root with the bundle-local venv. The wrapped
script is in the parent repo at `../convert_mjcf_urdf.py`. Pass an
**absolute** input path so the script doesn't try to resolve it
relative to the parent repo:

```bash
cd robot-assets-skills/
./.venv/bin/python ../convert_mjcf_urdf.py \
    "$(pwd)/robots/<robot>/<robot>.urdf" --to-mjcf
```

By default the output goes to the same directory with `.xml`
extension. To pick an explicit output path:

```bash
./.venv/bin/python ../convert_mjcf_urdf.py \
    "$(pwd)/robots/<robot>/<robot>.urdf" \
    "$(pwd)/robots/<robot>/<robot>.xml"
```

Verify the converted MJCF compiles:

```bash
./.venv/bin/python -c "
import mujoco
m = mujoco.MjModel.from_xml_path('robots/<robot>/<robot>.xml')
print('nq=', m.nq, 'nu=', m.nu, 'nbody=', m.nbody)
"
```

`nu` = 0 right after conversion is **expected** (no actuators yet);
that's one of the post-tune fixes. After fixing, `nu` should equal the
number of actuated joints.

View interactively to drive the sliders (`DISPLAY=:5` on our headless box):

```bash
DISPLAY=:5 ./.venv/bin/python -m mujoco.viewer \
    --mjcf robots/<robot>/<robot>.xml
```

If `.venv/` is missing or broken, bootstrap per `AGENTS.md`'s "Python
environment" section.

## References

- Step-by-step procedure: `references/workflow.md`
- The five post-tune fix categories with concrete recipes:
  `references/gotchas.md`
