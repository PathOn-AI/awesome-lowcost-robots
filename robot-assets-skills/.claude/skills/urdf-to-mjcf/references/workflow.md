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

3. **Inventory the URDF.** Note these counts before conversion — you'll
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
./.venv/bin/python ../convert_mjcf_urdf.py \
    "$(pwd)/robots/<robot>/<robot>.urdf" --to-mjcf
```

Output goes to `robots/<robot>/<robot>.xml` by default. Compile-check:

```bash
./.venv/bin/python -c "
import mujoco
m = mujoco.MjModel.from_xml_path('robots/<robot>/<robot>.xml')
print('nq=', m.nq, 'nu=', m.nu, 'nbody=', m.nbody)
"
```

`nu = 0` is **expected** at this stage — gotcha §3 fixes that.

## Post-tune (the work)

Each gotcha is a discrete edit to the converted MJCF. Apply in roughly
this order:

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

### Fix 4: Add contact excludes for palm-knuckle pairs

For dex hands: add `<contact><exclude>` entries for palm↔proximal-link
pairs (and any other adjacent-in-rest-pose pairs). See `gotchas.md` §4.

After fix 4, joints should reach their commanded targets without
sticking partway.

### Fix 5: Compiler / option attributes

Add `autolimits="true"` to `<compiler>` and `<option integrator="implicitfast"/>`
per `gotchas.md` §5.

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
   DISPLAY=:5 ./.venv/bin/python -m mujoco.viewer \
       --mjcf robots/<robot>/<robot>.xml
   ```
   Drive each actuator to its limits. Confirm:
   - Primary joint reaches target.
   - Mimic'd joints follow (visually proportional).
   - No joint sticks partway (would indicate missing contact excludes).
   - No numerical blowup (would indicate bad inertia or integrator).

## Register

Drop a `robot.json` in `robots/<robot>/`. Mjcf-only registration if
URDF + MJCF use different mesh dirs (e.g. URDF in `meshes/`, MJCF in
`assets/`):

```json
{
  "robot": {
    "name": "<owner>/<robot>",
    "display_name": "<Robot display name>",
    "description": "<short description>",
    "visibility": "official",
    "is_verified": true,
    "is_featured": false
  },
  "version": {
    "version": "1.0.0",
    "is_stable": true,
    "dof": <number of independent joints>,
    "motor_type": "<motor type>",
    "designer": "<original designer>",
    "urdf_file": null,
    "mjcf_file": "<robot>.xml",
    "meshes_dir": "assets",
    "changelog": "Initial release - hand-tuned MJCF from URDF source via urdf-to-mjcf skill. Added <equality> for N mimics, rescaled inertias, added M position actuators, palm-knuckle contact excludes, autolimits + implicitfast integrator."
  }
}
```

## Commit (when registering upstream)

The bundle's `robots/` is gitignored. To register in the parent repo:

```bash
cp -r robots/<robot>/ ../robots/<robot>/
cd ..
git add robots/<robot>/
git commit -m "Add <robot> MJCF (hand-tuned from URDF)"
git push origin main
```
