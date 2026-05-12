---
name: urdf-to-mjcf
description: Use when bringing a URDF robot, hand, or CAD-generated model into MuJoCo MJCF and no hand-tuned upstream MJCF exists.
---

# urdf-to-mjcf

Wrap `scripts/convert_urdf_to_mjcf.py`, which prefers K-Scale Labs
`urdf2mjcf` and falls back to MuJoCo's built-in URDF loader when that
package is unavailable. Then post-tune the output because raw
conversion is rarely usable as-is.

## Simulation boundary

Treat this skill as a **Level 0/1/1.5 generator**, not a calibrated
digital-twin generator:

- **Level 0: loadable.** XML compiles and opens in MuJoCo.
- **Level 1: controllable-ish.** Joints have plausible starter
  actuators and can be driven in the viewer.
- **Level 1.5: geometry-informed.** CAD/URDF provides credible link
  frames, collision/visual meshes, mass, and inertia.
- **Level 2: calibrated.** Requires real hardware or vendor data for
  torque-speed curves, controller gains, friction, backlash, armature,
  limits, and contact parameters. Do not invent this from geometry.

The wrapper prints `simulation_level`, `actuator_source`, and
`calibration_source`. If those say `generic_defaults`,
`template_estimate`, or `manual_override`, the model is a starting
point for simulation, not a validated physical model.

The script gets the kinematic tree right but does **not** handle:

1. **Mimic joints get silently dropped.** MuJoCo's URDF loader has no
   way to express URDF `<mimic>` semantics. All mimic'd joints become
   independent free joints; the underlying coupling is lost.
2. **Inertias are often 100x oversized.** Stock URDFs from xacro/SDF
   pipelines frequently use placeholder inertia values that produce
   absurd dynamics in MuJoCo (e.g. fingers that won't move at any
   reasonable kp).
3. **No calibrated actuators.** URDF has joints but no MuJoCo motor or
   controller model. The wrapper can add starter position actuators,
   but those are estimates unless supplied from hardware data.
4. **No contact excludes.** Adjacent links that touch in the rest pose
   (palm↔first-knuckle pairs are the typical case) get treated as
   active contacts and the joint physically can't reach its
   commanded angle.
5. **Converter schema quirks.** Known `urdf2mjcf` outputs can put
   `scale` on `<geom>` instead of `<mesh>`, add a fixed-arm
   `<freejoint>`, omit required inertial `pos`, and keep non-portable
   `file://` paths.
6. **No `autolimits`, no `implicitfast` integrator.** Defaults that
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
2. **Make xacro/URDF paths portable.** Replace ROS `$(find pkg)` and
   machine-local `file:///home/...` mesh paths with relative paths
   before conversion.
3. **Verify the URDF loads in MuJoCo standalone.** If MuJoCo can't
   parse it, the converter won't help — fix the URDF first.
4. Run the converter wrapper (see Commands). It applies deterministic
   fixes for scale placement, file URIs, missing inertial `pos`,
   fixed-base freejoints, compiler/option defaults, and basic joint
   dynamics.
5. **Classify the metadata source.** Decide whether this is Level 0,
   Level 1, or Level 1.5. Only call it Level 2 if actuator and
   dynamics parameters came from real hardware/vendor data and were
   validated against motion.
6. **Post-tune the MJCF.** Walk through the fix categories in
   `references/gotchas.md`: mimics→`<equality>`, inertias,
   actuators, contact excludes, mesh-origin problems, and tuned
   dynamics.
7. **Verify in the viewer.** Each actuator slider should drive the
   intended joint(s) to the commanded angle without numerical
   blowup or contact-blocked motion.

## Commands

Run from the bundle root with the bundle-local venv. The wrapped
script ships with this skill. Pass an explicit output path:

```bash
cd robot-assets-skills/
./.venv/bin/python .claude/skills/urdf-to-mjcf/scripts/convert_urdf_to_mjcf.py \
    robots/<robot>/<robot>.urdf \
    robots/<robot>/<robot>.xml
```

For an SO101-style arm using STS3215-class servos as a starter
template, use the explicit profile. It is still an estimate:

```bash
./.venv/bin/python .claude/skills/urdf-to-mjcf/scripts/convert_urdf_to_mjcf.py \
    robots/<robot>/<robot>.urdf \
    robots/<robot>/<robot>.xml \
    --control-profile so101-sts3215
```

For a new CAD arm with unknown hardware, stay with the generic profile
or override parameters explicitly:

```bash
./.venv/bin/python .claude/skills/urdf-to-mjcf/scripts/convert_urdf_to_mjcf.py \
    robots/<robot>/<robot>.urdf \
    robots/<robot>/<robot>.xml \
    --position-kp 15 \
    --position-force 3.35 \
    --joint-damping 0.6 \
    --joint-armature 0.028 \
    --joint-frictionloss 0.052
```

If using the vendored converter from `pathonai_diy_pipeline` without
installing it into `.venv`, the wrapper checks this default path:

```text
/home/aidy/Projects/pathonai_diy_pipeline/scripts/urdf2mjcf
```

Override it when needed:

```bash
URDF2MJCF_VENDOR_PATH=/path/to/scripts/urdf2mjcf \
./.venv/bin/python .claude/skills/urdf-to-mjcf/scripts/convert_urdf_to_mjcf.py \
    robots/<robot>/<robot>.urdf \
    robots/<robot>/<robot>.xml
```

Verify the converted MJCF compiles:

```bash
./.venv/bin/python -c "
import mujoco
m = mujoco.MjModel.from_xml_path('robots/<robot>/<robot>.xml')
print('nq=', m.nq, 'nu=', m.nu, 'nbody=', m.nbody)
"
```

If the wrapper falls back to MuJoCo's built-in loader, raw conversion
would produce `nu = 0`; the postprocess step adds starter position
actuators where possible. If K-Scale `urdf2mjcf` runs, generated
motors are converted to position actuators by default unless
`--keep-motors` is passed.

View interactively to drive the sliders (set `$DISPLAY` first if headless — see `AGENTS.md`):

```bash
./.venv/bin/python -m mujoco.viewer \
    --mjcf robots/<robot>/<robot>.xml
```

If `.venv/` is missing or broken, bootstrap per `AGENTS.md`'s "Python
environment" section, then install this skill's requirements.

## References

- Step-by-step procedure: `references/workflow.md`
- The five post-tune fix categories with concrete recipes:
  `references/gotchas.md`
