# `attach-end-effector` Workflow

Full step-by-step procedure for combining an arm and an end-effector
into a single MJCF model. Pair this with `gotchas.md` — every step has
a known way to go wrong.

## Preflight

1. Confirm the arm has `<site name="attachment_site" .../>` in its
   wrist link with `pos`/`quat` defining the wrist flange frame. For
   `piper_arm`, this is at link6 with `pos="0 0 0" quat="1 0 0 0"`.
2. Confirm the end-effector MJCF compiles standalone:
   ```bash
   ./.venv/bin/python -c "
   import mujoco
   m = mujoco.MjModel.from_xml_path('robots/<eef>/<eef>.xml')
   print('eef nq=', m.nq, 'nu=', m.nu)
   "
   ```
3. Confirm MuJoCo Python is ≥ 3.5 (see `gotchas.md` §6).
4. **Predict the prefix.** Default to a non-empty prefix. Empty prefix
   has two failure modes (entity-name collisions AND bare nested
   `<default>` blocks); see `gotchas.md` §3 for the two `grep` checks
   that decide whether empty is actually safe. When in doubt, use a
   non-empty prefix — the cost is zero.
5. **Predict the mount pos + quat.** Run the bundled helper to compute
   the full mounting transform (no eyeballing). Pass BOTH the arm and
   the eef so the helper can read the arm's `attachment_site` quat and
   express the mount in wrist body frame:
   ```bash
   ./.venv/bin/python .claude/skills/attach-end-effector/scripts/compute_wrist_mount.py \
       robots/<eef>/<eef>.xml --arm robots/<arm>/<arm>.xml
   ```
   It prints a single `pos="..." quat="..."` line to apply on the
   prefixed root body in the combined XML (Fix 3 below). If the palm
   visually mounts rotated (palm facing wrong way, fingers poking the
   arm), re-run with `--twist 90 / 180 / 270` until it looks right.
   See `gotchas.md` §2 for why we use the collision-flush convention.
6. **Read the eef's `<compiler meshdir>`.** The attach script assumes
   `<eef>/assets/`. If the gripper's compiler element points elsewhere
   (e.g. `meshes`, unset, etc.), the script silently copies zero
   gripper meshes. See `gotchas.md` §4 for the parse + copy recipe;
   you'll need it in Fix 1 below.

## Attach

The bundle's venv is at `robot-assets-skills/.venv/`. The wrapped
script `attach_arm_end_effector.py` ships in this skill at
`.claude/skills/attach-end-effector/scripts/attach_arm_end_effector.py`.
The script resolves relative `--arm` / `--end-effector` / `--output`
paths against its own directory, so we pass **absolute** paths via
`$(pwd)/` to make the bundle's `robots/` the working directory.

```bash
cd robot-assets-skills/
./.venv/bin/python .claude/skills/attach-end-effector/scripts/attach_arm_end_effector.py \
    --arm          "$(pwd)/robots/<arm>/<arm>.xml" \
    --end-effector "$(pwd)/robots/<eef>/<eef>.xml" \
    --output       "$(pwd)/robots/<arm>_<eef>" \
    --prefix       "<prefix>_" \
    --no-viewer
```

The script writes:

- `robots/<arm>_<eef>/<arm>_<eef>.xml` — the combined MJCF
- `robots/<arm>_<eef>/<arm>_<eef>.mjb` — binary cache (often >50 MB,
  triggers GitHub LFS warning; see repo `.mjb` policy)
- `robots/<arm>_<eef>/scene.xml` — wraps the MJCF with a floor +
  lighting for viewer use
- `robots/<arm>_<eef>/README.md` — generated description
- `robots/<arm>_<eef>/assets/` — merged mesh dir from arm + eef

## Post-attach fixes

### Fix 1: gripper mesh copy (always run — script's stdout will lie)

The script reports "Copying mesh assets..." but only actually copies
files from the *arm's* `assets/` dir if the gripper's mesh dir isn't
literally `assets/`. See `gotchas.md` §4. Always do this:

```bash
# Resolve the gripper's actual mesh dir from its <compiler meshdir="...">
EEF_XML=robots/<eef>/<eef>.xml
EEF_MESHDIR=$(./.venv/bin/python -c "
import xml.etree.ElementTree as ET, pathlib
xml = pathlib.Path('$EEF_XML')
comp = ET.parse(xml).getroot().find('compiler')
md = (comp.get('meshdir') if comp is not None else None) or '.'
print((xml.parent / md).resolve())
")
cp -n "$EEF_MESHDIR"/* robots/<arm>_<eef>/assets/
```

`cp -n` (no-clobber) preserves anything copied by the script and any
prefix-renamed files from Fix 2 below.

Sanity-check the merged dir picked up the eef meshes:

```bash
echo "arm:      $(ls robots/<arm>/assets/ | wc -l)"
echo "eef:      $(ls "$EEF_MESHDIR" | wc -l)"
echo "combined: $(ls robots/<arm>_<eef>/assets/ | wc -l)"
# combined should equal arm + eef (minus same-name overwrites — see Fix 2)
```

### Fix 2: mesh-filename collisions (always check, BOTH directions)

Same-named meshes between arm and eef can land wrong in two ways:
the script copies arm first and the eef's same-name version is
silently dropped (Direction A), OR the arm's `meshdir` isn't
`assets/`, the script's hardcoded copy step finds zero arm meshes,
the eef's meshes land first, and Fix 1's `cp -n` then can't
overwrite them with the arm's correct version (Direction B). Either
way: a same-name file ends up under one body's reference but with
the other body's content.

```bash
# List size mismatches between BOTH source dirs and the merged combined assets
python3 -c "
from pathlib import Path
arm = Path('$ARM_MESHDIR')        # resolved analogously to Fix 1
eef = Path('$EEF_MESHDIR')        # resolved by Fix 1 above
combined = Path('robots/<arm>_<eef>/assets')
for src, label in [(arm, 'ARM'), (eef, 'EEF')]:
    if not src.exists(): continue
    for f in src.iterdir():
        cf = combined / f.name
        if cf.exists() and cf.stat().st_size != f.stat().st_size:
            print(f'COLLISION ({label}):', f.name, f.stat().st_size, '->', cf.stat().st_size)
"
```

If any `COLLISION:` lines print (in either direction), run
`gotchas.md` §1 fix — it batches all collisions and handles both
directions in one pass.

### Fix 3: pos + quat mount (when the script's output mounts wrong)

Get the recommended `pos="..." quat="..."` line from
`compute_wrist_mount.py` (the preflight step ran it already; re-run if
you skipped, or to dial in `--twist`). Then edit the combined MJCF
in-place to override the prefixed root body's pose:

```bash
sed -i 's|<body name="<prefix>_<root>" childclass="<prefix>_<class>" quat="<auto-quat>">|<body name="<prefix>_<root>" childclass="<prefix>_<class>" pos="<X> <Y> <Z>" quat="<W> <X> <Y> <Z>">|' \
    robots/<arm>_<eef>/<arm>_<eef>.xml
```

See `gotchas.md` §2 for why we use the collision-flush convention,
and why pos/quat must be expressed in the wrist body frame (not the
site frame).

### Fix 4: tendon hands

If the end-effector source has `<tendon>` actuators or `<sensor>`
entries, run the checks in `gotchas.md` §5. The attach script may
compile while dropping most tendon actuators.

## Verify

1. **Compile + count check:**
   ```bash
   ./.venv/bin/python -c "
   import mujoco
   m = mujoco.MjModel.from_xml_path('robots/<arm>_<eef>/<arm>_<eef>.xml')
   print('combined nq=', m.nq, 'nu=', m.nu, 'nbody=', m.nbody, 'ntendon=', m.ntendon, 'neq=', m.neq)
   for i in range(m.nu):
       print(' ', i, m.actuator(i).name)
   "
   ```
   Expected: `nq = arm.nq + eef.nq`, `nu = arm.nu + eef.nu`, all
   actuator names prefixed correctly. For tendon hands, also compare
   `ntendon`, tendon actuator names, and sensor names against the eef
   source.

2. **Visual check** (must — collisions and pos offsets are visual bugs
   that compile cleanly):
   ```bash
   ./.venv/bin/python -m mujoco.viewer \
       --mjcf robots/<arm>_<eef>/scene.xml
   ```
   Drag actuator sliders to confirm:
   - Arm joints move only the arm.
   - End-effector joints move only the end-effector.
   - End-effector mounts flush at the wrist flange (no gap, no clipping).
   - Visual geometry looks correct (no "mystery box" — that's a mesh
     collision; see `gotchas.md` §1).

## Commit (when promoting the combined model upstream)

The bundle's `robots/` is gitignored — nothing here gets committed
from inside the bundle. To promote a combined model into the parent
repo (`pathonai_robot_assets`), copy the combined folder out:

```bash
cp -r robots/<arm>_<eef>/ ../robots/<arm>_<eef>/
cd ..
git add robots/<arm>_<eef>/
git commit -m "Add <arm>_<eef> combined model"
git push origin main
```

The combined `.mjb` is large (~50–80 MB). Current parent-repo policy
is to commit it (matching `piper_arm_barrett`); GitHub will warn but
accept. If `.mjb` ever gets gitignored, document the regen recipe in
the combined `README.md`.
