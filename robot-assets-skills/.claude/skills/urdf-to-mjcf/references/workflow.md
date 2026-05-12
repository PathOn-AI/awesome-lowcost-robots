# `urdf-to-mjcf` Workflow

Full step-by-step procedure for converting a URDF to a working MJCF.
Pair this with `gotchas.md` — the auto-conversion is the *easy* part;
the post-tune is where every iteration of this skill has been spent.

## Preflight

1. **Check `mujoco_menagerie` first.** Search
   `https://github.com/google-deepmind/mujoco_menagerie` for your
   robot:
   ```bash
   git clone --depth 1 https://github.com/google-deepmind/mujoco_menagerie.git /tmp/mujoco_menagerie
   ls /tmp/mujoco_menagerie/ | grep -i <robot-name>
   ```
   If found, copy its MJCF + assets into `robots/<robot>/` and **stop
   — don't run the converter**. The MuJoCo team has tuned it; you
   won't beat their work by re-running URDF→MJCF.

2. Confirm the URDF parses standalone (sanity check that the URDF
   itself isn't broken):
   ```bash
   ./.venv/bin/python -c "
   import mujoco
   m = mujoco.MjModel.from_xml_path('robots/<robot>/<robot>.urdf')
   print('parsed: nq=', m.nq, 'nbody=', m.nbody)
   "
   ```
   If MuJoCo can't parse it, fix the URDF before the converter; the
   converter uses the same loader.

3. **Make mesh paths portable before conversion.** Xacro/URDF exported
   from ROS workspaces often contains `$(find pkg)`, `package://...`,
   or `file:///home/<user>/...` paths. Prefer regenerating from a
   standalone xacro:
   ```bash
   cd robots/<robot>/
   sed 's|$(find <package_name>)|<package_name>|g' \
       <package_name>/urdf/<robot>.xacro > <robot>.xacro
   ../../.venv/bin/xacro <robot>.xacro > <robot>.urdf
   ```
   Then verify mesh references are relative to the robot folder.

4. **Classify available metadata before conversion.** This sets the
   right expectation for the generated MJCF:
   - CAD/URDF can provide link frames, mesh scale, visual/collision
     geometry, approximate mass, and approximate inertia.
   - CAD/URDF cannot reliably provide torque-speed curves, gear ratio,
     controller gains, backlash, friction, armature, contact
     parameters, or calibrated soft limits.
   - Without hardware/vendor data, the output target is Level 1 or
     Level 1.5, not Level 2.

5. **Inventory the URDF.** Note these counts before conversion — you'll
   need them to detect dropped mimics:
   ```bash
   grep -c '<joint name=' robots/<robot>/<robot>.urdf       # total joints (incl mimic)
   grep -c '<mimic ' robots/<robot>/<robot>.urdf            # mimic count
   grep -c 'type="revolute"\|type="prismatic"' robots/<robot>/<robot>.urdf
   ```
   `total - mimic = number of independent (controllable) joints`. The
   converted MJCF should ultimately have that many actuators (gotcha §3).

## Convert

From the bundle root, with the bundle-local venv:

```bash
cd robot-assets-skills/
./.venv/bin/python .claude/skills/urdf-to-mjcf/scripts/convert_urdf_to_mjcf.py \
    robots/<robot>/<robot>.urdf \
    robots/<robot>/<robot>.xml
```

The wrapper prefers K-Scale `urdf2mjcf`. If the package is not
installed, it tries the vendored source at
`/home/aidy/Projects/pathonai_diy_pipeline/scripts/urdf2mjcf`. If
that cannot import, it falls back to MuJoCo's built-in URDF loader and
prints `engine=mujoco`.

The wrapper also prints provenance:

```text
simulation_level=level_1_controllable
actuator_source=position_actuators:<profile>
calibration_source=<generic_defaults|template_estimate|manual_override>
```

Read this as a boundary marker. `generic_defaults`,
`template_estimate`, and `manual_override` are not calibrated physics.

Install the stronger converter into the bundle venv when needed:

```bash
./.venv/bin/pip install -e /home/aidy/Projects/pathonai_diy_pipeline/scripts/urdf2mjcf
```

Compile-check:

```bash
./.venv/bin/python -c "
import mujoco
m = mujoco.MjModel.from_xml_path('robots/<robot>/<robot>.xml')
print('nq=', m.nq, 'nu=', m.nu, 'nbody=', m.nbody)
"
```

If `--no-postprocess` is used, `nu = 0` is expected for MuJoCo
built-in conversion. With default postprocess, the wrapper adds
starter position actuators where it can infer joint ranges. K-Scale
`urdf2mjcf` may create default motor actuators, but the wrapper
converts those to position actuators unless `--keep-motors` is passed.

## Post-tune (the work)

The wrapper already applies deterministic fixes learned from the
January/February sprint logs:

- move `scale` from mesh geoms to `<asset><mesh>`
- strip `file://` mesh URI prefixes
- add missing `pos="0 0 0"` to inertials
- remove converter-added `<freejoint>` for fixed-base arms
- set `compiler autolimits="true"` and `option integrator="implicitfast"`
- add basic joint damping/armature when missing
- convert generic torque `<motor>` actuators to `<position>` actuators
  with joint `ctrlrange`, so viewer sliders behave as target angles

Generic defaults are intentionally modest starter estimates:

```text
position kp=30
position forcerange=-12 12
joint damping=0.5
joint armature=0.01
```

For SO101/STS3215-style starting points from the sprint logs:

```bash
./.venv/bin/python .claude/skills/urdf-to-mjcf/scripts/convert_urdf_to_mjcf.py \
    robots/<robot>/<robot>.urdf \
    robots/<robot>/<robot>.xml \
    --control-profile so101-sts3215
```

That profile uses:

```text
position kp=17.8
position forcerange=-3.35 3.35
joint damping=0.60
joint armature=0.028
joint frictionloss=0.052
```

Use command-line overrides when the CAD or hardware team gives better
values. Keep a note in the robot folder describing where the numbers
came from.

Then apply the judgment-heavy fixes in roughly this order:

### Fix 1: Re-add mimic relationships as `<equality>`

If `mimic_count > 0` from preflight, the converted MJCF is missing
those constraints. Add an `<equality>` block per `gotchas.md` §1 with
one `<joint>` element per mimic relationship.

After fix 1, viewer should show driving the primary joint also moves
the mimic'd joint(s).

### Fix 2: Rescale inertias

Inspect each link's `<inertial>` per `gotchas.md` §2. Override the
ones that are 100x outside reasonable values. For dex hands,
copy from menagerie's hand-tuned inertias as reference.

### Fix 3: Add actuators

Add a `<default>` class with `kp`/`kv` defaults, then a `<actuator>`
block with one `<position>` per *primary* joint (not mimics — those
are driven via the `<equality>`). See `gotchas.md` §3 for the template.

After fix 3, the viewer should show one slider per controllable joint,
and dragging a slider should drive the joint to the target.

If dragging a slider responds slowly, check whether the output still
has `<motor>` actuators. Torque motors make the slider a force command;
position actuators make it a target-angle command.

If the joint jitters or oscillates, lower `--position-kp` or
`--position-force`, and increase `--joint-damping` or
`--joint-armature` in small steps. These values should be copied from
hardware/controller data when available; viewer tuning alone is still
an estimate.

### Fix 4: Add contact excludes for palm-knuckle pairs

For dex hands: add `<contact><exclude>` entries for palm↔proximal-link
pairs (and any other adjacent-in-rest-pose pairs). See `gotchas.md` §4.

After fix 4, joints should reach their commanded targets without
sticking partway.

### Fix 5: Mesh-origin / mesh-format sanity

If links appear bunched at the origin, do not assume the XML kinematic
tree is wrong. Compare body and geom offsets against the URDF, then
check whether meshes were converted from DAE to STL/OBJ and lost
internal origin/scale metadata. See `gotchas.md` §6.

### Fix 6: Compiler / option attributes

The wrapper sets these automatically, but verify `autolimits="true"`
and `<option integrator="implicitfast"/>` survived any later hand edit.

## Verify

1. **Compile + count check:**
   ```bash
   ./.venv/bin/python -c "
   import mujoco
   m = mujoco.MjModel.from_xml_path('robots/<robot>/<robot>.xml')
   print('nq=', m.nq, 'nu=', m.nu)
   for i in range(m.nu):
       print(' ', i, m.actuator(i).name, '->', m.joint(m.actuator(i).trnid[0]).name)
   "
   ```
   Expected: `nu = independent_joints` from preflight. Each actuator
   maps to one primary joint.

2. **Equality count:**
   ```bash
   ./.venv/bin/python -c "
   import mujoco
   m = mujoco.MjModel.from_xml_path('robots/<robot>/<robot>.xml')
   print('eq:', m.neq)
   "
   ```
   Expected: `neq = mimic_count` from preflight.

3. **Viewer test** (must — most fix-ups are visual/dynamic, not
   compile-time):
   ```bash
   ./.venv/bin/python -m mujoco.viewer \
       --mjcf robots/<robot>/<robot>.xml
   ```
   Drive each actuator to its limits. Confirm:
   - Primary joint reaches target.
   - Mimic'd joints follow (visually proportional).
   - No joint sticks partway (would indicate missing contact excludes).
   - No numerical blowup (would indicate bad inertia or integrator).

## Commit (when adding to the parent repo)

The bundle's `robots/` is gitignored. To track the MJCF in the parent repo:

```bash
cp -r robots/<robot>/ ../robots/<robot>/
cd ..
git add robots/<robot>/
git commit -m "Add <robot> MJCF (hand-tuned from URDF)"
git push origin main
```
