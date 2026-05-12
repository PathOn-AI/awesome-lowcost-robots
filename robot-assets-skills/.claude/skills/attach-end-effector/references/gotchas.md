# `attach-end-effector` Gotchas

Concrete failure modes the underlying `attach_arm_end_effector.py` doesn't
handle, with the fix recipe for each. Read this before declaring an
attach "done".

---

## 1. Mesh-filename collisions silently render the wrong geometry

**Symptom.** End-effector OR arm visual looks completely wrong (wrong
shape, wrong size, often a "huge mystery box" hovering near the wrist),
OR the model fails to compile with
`Error: 'inertia must have positive eigenvalues'` — MuJoCo computed
inertia from the wrong mesh content for that body.

**Two causes (same root issue, two directions).** The combined
`assets/` dir ends up with a single file under a name that *both* the
arm and the eef expect to map to *different* mesh content. Whichever
mesh-ref happens to point at the wrong content sees garbage.

- **Direction A (script-side, arm wins).** The script copies arm
  assets first, then end-effector assets, with
  `if not dest_file.exists(): copy`. If both arm and eef ship a
  STL/OBJ with the same basename and the arm's version lands first,
  the eef's version is silently dropped. The eef's `<mesh file=...>`
  ref then resolves to the arm's mesh content. *Concrete example:*
  Piper arm's `base_link.stl` (535 KB) and allegro_right's
  `base_link.stl` (164 KB) — `<mesh name="right_base_link"
  file="base_link.stl"/>` rendered the piper arm-base as the allegro
  palm.

- **Direction B (post-script, eef wins).** When the arm's
  `<compiler meshdir>` isn't `assets/`, the script's hardcoded copy
  step finds zero arm meshes (gotcha §4), so the eef's meshes land
  in the combined `assets/` first. After applying the §4 fix
  (`cp -n` arm's meshdir → combined `assets/`), the eef's same-named
  mesh is already there and the no-clobber `cp` skips the arm's
  version. The arm's `<mesh file=...>` ref then resolves to the
  eef's mesh content — frequently triggering the inertia error
  above. *Concrete example:* SO101_6dof_arm + allegro_right — both
  ship `base_link.stl`; the eef's 164KB palm mesh sat in combined
  `assets/` and the arm's 1.1MB arm-base body inherited it,
  producing degenerate inertia.

**Detection.** Diff the combined `assets/` against BOTH the arm's
mesh source AND the eef's mesh source. Any same-named file with a
size mismatch on either side is a collision.

```bash
ARM_MESHDIR=$(./.venv/bin/python -c "
import xml.etree.ElementTree as ET, pathlib
xml = pathlib.Path('robots/<arm>/<arm>.xml')
comp = ET.parse(xml).getroot().find('compiler')
md = (comp.get('meshdir') if comp is not None else None) or '.'
print((xml.parent / md).resolve())")
EEF_MESHDIR=$(./.venv/bin/python -c "
import xml.etree.ElementTree as ET, pathlib
xml = pathlib.Path('robots/<eef>/<eef>.xml')
comp = ET.parse(xml).getroot().find('compiler')
md = (comp.get('meshdir') if comp is not None else None) or '.'
print((xml.parent / md).resolve())")

echo '--- arm vs combined ---'  # any size mismatch = Direction B
diff <(stat -c '%n %s' "$ARM_MESHDIR"/* | sed 's|.*/||') \
     <(stat -c '%n %s' robots/<arm>_<eef>/assets/*  | sed 's|.*/||')
echo '--- eef vs combined ---'  # any size mismatch = Direction A
diff <(stat -c '%n %s' "$EEF_MESHDIR"/* | sed 's|.*/||') \
     <(stat -c '%n %s' robots/<arm>_<eef>/assets/*  | sed 's|.*/||')
```

**Fix.** For every collision, prefix-rename the EEF's copy in
combined `assets/` and rewrite the eef's `<mesh file=...>` ref to
point at the prefixed name. Then ensure the arm's correct mesh
content sits at the bare basename. The snippet below handles both
directions in one pass: it walks all eef meshes, prefix-renames any
that collide with arm-side content (regardless of which version
currently sits in combined), and overwrites the bare basename with
the arm's version.

```bash
# Inputs — adjust to your run
PREFIX="<prefix>_"           # must match the --prefix passed to the script
ARM_EEF=<arm>_<eef>          # e.g. so101_6dof_arm_allegro_right
ARM_XML=robots/<arm>/<arm>.xml
EEF_XML=robots/<eef>/<eef>.xml

ARM_MESHDIR=$(./.venv/bin/python -c "
import xml.etree.ElementTree as ET, pathlib
xml = pathlib.Path('$ARM_XML')
comp = ET.parse(xml).getroot().find('compiler')
md = (comp.get('meshdir') if comp is not None else None) or '.'
print((xml.parent / md).resolve())")
EEF_MESHDIR=$(./.venv/bin/python -c "
import xml.etree.ElementTree as ET, pathlib
xml = pathlib.Path('$EEF_XML')
comp = ET.parse(xml).getroot().find('compiler')
md = (comp.get('meshdir') if comp is not None else None) or '.'
print((xml.parent / md).resolve())")

PREFIX="$PREFIX" ARM_MESHDIR="$ARM_MESHDIR" EEF_MESHDIR="$EEF_MESHDIR" \
ARM_EEF="$ARM_EEF" ./.venv/bin/python - <<'PYEOF'
import os, re, shutil
from pathlib import Path

prefix = os.environ['PREFIX']
arm = Path(os.environ['ARM_MESHDIR'])
eef = Path(os.environ['EEF_MESHDIR'])
combined = Path('robots') / os.environ['ARM_EEF']
assets = combined / 'assets'
xml_path = combined / (combined.name + '.xml')

text = xml_path.read_text()
arm_files = {f.name: f for f in arm.iterdir()} if arm.exists() else {}
collisions = []
for f in eef.iterdir():
    arm_match = arm_files.get(f.name)
    if arm_match is None:
        continue
    # Same name on both sides; if content differs it's a collision.
    if f.stat().st_size != arm_match.stat().st_size:
        collisions.append((f, arm_match))

for eef_file, arm_file in collisions:
    new_name = f"{prefix}{eef_file.name}"
    shutil.copy(eef_file, assets / new_name)              # eef under prefixed name
    shutil.copy(arm_file, assets / eef_file.name)         # arm under bare name (overwrites)
    # IMPORTANT: scope the rewrite to mesh refs whose `name=` starts with
    # the eef prefix. Otherwise a naive `file="<basename>"` regex also
    # matches the ARM's mesh ref (which has the same `file=` value but a
    # bare/unprefixed `name=`) and re-points it at the wrong file.
    pat = re.compile(
        rf'(<mesh\b[^/>]*\bname="{re.escape(prefix)}[^"]*"[^/>]*\bfile=")'
        rf'({re.escape(eef_file.name)})(")'
    )
    text, n = pat.subn(rf'\1{new_name}\3', text)
    if n == 0:
        # Some MJCFs put `file=` before `name=`; try the swapped order.
        pat2 = re.compile(
            rf'(<mesh\b[^/>]*\bfile=")({re.escape(eef_file.name)})("[^/>]*\bname="{re.escape(prefix)}[^"]*")'
        )
        text, n = pat2.subn(rf'\1{new_name}\3', text)
    print(f"  {eef_file.name}  ->  {new_name}   "
          f"(eef ref(s) updated: {n}; arm copy refreshed under bare name)")

xml_path.write_text(text)
print(f"Resolved {len(collisions)} collision(s)")
PYEOF
```

Reload in viewer (or recompile) to confirm. If `Resolved 0
collision(s)` prints, you're clean — re-run both detection diffs
above to confirm.

**Prevention going forward.** Any time arm and end-effector both ship
a mesh with the same basename, plan the rename ahead of time (do
step 1+2 *before* step 5 of the workflow). Direction B is especially
sneaky because it surfaces only after the §4 mesh-source fix masks
the gap.

---

## 2. End-effector mounts at the wrong pos / orientation on the wrist

**Symptom.** End-effector mounts at the wrist but with one or more of:
- Palm body extends *into the arm* (back of palm hidden inside the
  wrist link).
- Palm/fingers point in the wrong direction (sideways, up, or back
  toward the arm) instead of "out of the flange".
- One or more finger bodies clip into the wrist link.

**Cause.** Three independent things the attach script gets wrong:

1. **Origin on the wrong face.** Some standalone MJCFs (notably
   mujoco_menagerie's wonik_allegro left/right_hand.xml) place the
   palm body's *origin* at the **front face** of the palm — where the
   fingers attach — with palm geometry extending in palm-local -Z. So
   the back of the palm sits ~5–10 cm into the arm.
2. **Standalone palm quat composed with site quat.** The script
   preserves the standalone palm body's quat, which then composes with
   the arm's `attachment_site` quat. The standalone quat was authored
   for the eef sitting in worldbody, not on this arm's flange; the
   composition rarely produces the right orientation.
3. **`pos` is in wrist body frame, not site frame.** The arm's
   `attachment_site` may have a non-trivial quat (e.g. SO101's site is
   +90° around Y). A naive `pos="0 0 H"` on the palm body translates
   along *wrist body Z*, which can be world-up or sideways — NOT
   along the flange-out direction.

**Detection.** Run the bundled helper. Pass BOTH the arm and the eef
so it can read the site's quat + pos and express the mount in the
correct (wrist body) frame:

```bash
./.venv/bin/python .claude/skills/attach-end-effector/scripts/compute_wrist_mount.py \
    robots/<eef>/<eef>.xml --arm robots/<arm>/<arm>.xml
```

It computes:
- `Q_align` — rotation that maps the eef's auto-detected fingers-out
  axis (centroid of root descendants) to site +Z.
- `Q_palm = Q_site * Q_twist * Q_align` — the palm body's quat in the
  wrist body frame.
- `H` — negative-Z extent of the root body's COLLISION geoms in site
  frame (post-rotation), so the back of the palm sits flush with the
  flange.
- `pos = site_pos + R(Q_site) @ (0, 0, H)` — translation along site
  +Z, expressed in wrist body coords.

The helper reports two H values:
- `H (collision-flush)` — uses only collision geoms (`contype |
  conaffinity != 0`). Recommended: contact volumes sit flush with the
  wrist flange.
- `H (visual + collision union)` — includes visual meshes. Usually
  larger because real eef hardware extends behind the palm origin
  (cables, mounting plate). Don't use this — it pushes the eef forward,
  leaving a contact gap at the wrist.

**Fix.** Override the prefixed root body's pos + quat with the
helper's output. Both must be applied together — using one without
the other reproduces the original problem.

```bash
# Before (script's default)
<body name="<prefix>_palm" childclass="..." quat="<auto-quat>">
# After (use the pos and quat printed by compute_wrist_mount.py)
<body name="<prefix>_palm" childclass="..." pos="<X> <Y> <Z>" quat="<W> <X> <Y> <Z>">
```

**Twist limitation.** The auto-detected quat aligns the palm's
fingers-out axis with site +Z, but the rotation *around* that axis
(palm-up vs palm-down vs thumb-side) is convention-dependent and
under-determined by descendant geometry alone. If the palm visually
mounts with fingers projecting toward the arm or with the palm facing
the wrong way, re-run with `--twist {90,180,270}` until it looks
right. The helper recomputes pos and quat for each twist value.

**Multi-geom limitation (visible gap at the mount face).** When the
root body has multiple collision geoms with different -Z extents
(e.g. PincOpen has both an `interface_arm100` mounting plate AND a
`base` body whose mesh origin sits forward of the body origin), the
helper auto-picks the DEEPEST geom — guaranteeing no geom penetrates
the arm. The shallower geom (the actual mount face) then sits
forward of the flange, leaving a visible gap.

The helper output flags this with `MULTI-GEOM NOTE` and prints a
per-geom `H` column. Pick the H of the geom that's the real mounting
interface and pass it via `--h-override`:

```bash
./.venv/bin/python .claude/skills/attach-end-effector/scripts/compute_wrist_mount.py \
    robots/PincOpen/gripper.xml --arm robots/piper_arm/piper_arm.xml \
    --h-override 0.0066    # interface_arm100 plate, not base body
```

The deeper geom will then visually overlap the wrist link (typically
hidden inside its mesh), but the actual mount face sits flush.

**Prevention.** Run `compute_wrist_mount.py` in the preflight step
*before* attaching, not after seeing clipping in the viewer.

---

## 3. Empty prefix is risky — default to a non-empty prefix

Empty `--prefix ""` has two distinct failure modes. Internal namespacing
(e.g. barrett's `bh_*`) only protects against the first one — not the
second.

**Failure mode A: name collision on entities.** Both arm and
end-effector declare an entity with the same name (mesh, joint, body,
material, etc.). With empty prefix the script errors out with
`ValueError: repeated name 'X' in mesh` during attach.

- *Example.* piper + allegro: both declare `<mesh name="base_link" .../>`.
  Empty prefix fails with `repeated name 'base_link' in mesh`.

**Failure mode B: unnamed nested `<default>` block.** The end-effector's
standalone MJCF has a *bare* `<default>` (no `class=` attr) wrapping its
real default classes. This is legal at the document root (where MJCF
allows one anonymous root-default), but after attach the gripper's
defaults get nested under the arm's outer `<default>`, and an unnamed
nested default is illegal — MuJoCo rejects with
`XML Error: empty class name, Element 'default'`. A non-empty prefix
gives the bare default a name (`<default class="<prefix>main">`), which
is well-formed.

- *Example.* piper + barrett: empty prefix compiles via attach but fails
  on the *next* load with `empty class name`. Barrett's source XML wraps
  `<default class="bhand">` in a bare `<default>`. The internal `bh_*`
  joint/mesh names are irrelevant — the failure is about default-class
  naming, not entity collisions.

**Detection.** Empty prefix is a footgun. Before passing it, check both:

```bash
# A: any name overlap between arm and eef defs?
grep -hE '<(mesh|joint|body|material) name=' robots/<arm>/<arm>.xml robots/<eef>/<eef>.xml \
  | sed -E 's/.*name="([^"]+)".*/\1/' | sort | uniq -d

# B: any bare <default> in the eef (no class= attr)?
grep -E '<default(>| [^c])' robots/<eef>/<eef>.xml
```

If either prints anything, use a non-empty prefix.

**Fix.** Default to a non-empty prefix unless you've explicitly verified
both checks above are clean. The cost of a prefix is zero; the failures
above are silent until compile/load.

---

## 4. End-effector meshes are not always under `assets/`

**Symptom.** Combined model fails to load with
`Error: could not open file 'assets/<some-mesh>.obj'`. The combined
`assets/` dir is missing the end-effector's mesh files entirely. The
script's stdout shows only the arm's mesh-copy line — no count for the
gripper.

**Cause.** `attach_arm_end_effector.py` hard-codes the end-effector's
mesh source as `eef_path.parent / "assets"`. End-effectors whose
`<compiler meshdir="..."/>` points anywhere else (e.g. `meshes`,
`../shared/meshes`, or unset — meaning the directory of the XML file
itself) are silently skipped: the dir doesn't exist, the loop is empty,
no warning is printed.

- *Example we hit.* `barrett_hand.xml` has
  `<compiler meshdir="meshes" .../>`. The script looked in
  `robots/barrett_hand/assets/`, found nothing, and emitted no warning.
  Combined XML still references `palm_282.dae.obj` etc., causing load
  failure.

**Detection.** Right after the script finishes:

```bash
# Total files in combined assets/ should equal arm + eef (minus collisions)
ls robots/<arm>/assets/ | wc -l       # arm count
ls robots/<arm>_<eef>/assets/ | wc -l # combined count — should be arm + eef
```

If short by ~the eef's mesh count, this is the bug.

**Fix.** Parse the gripper's actual `meshdir` from its compiler element
and copy from there. Don't assume `assets/` *or* `meshes/` — read the
XML:

```bash
EEF_XML=robots/<eef>/<eef>.xml
EEF_MESHDIR=$(./.venv/bin/python -c "
import xml.etree.ElementTree as ET, pathlib
xml = pathlib.Path('$EEF_XML')
root = ET.parse(xml).getroot()
comp = root.find('compiler')
md = (comp.get('meshdir') if comp is not None else None) or '.'
print((xml.parent / md).resolve())
")
cp -n "$EEF_MESHDIR"/* robots/<arm>_<eef>/assets/
```

The `cp -n` (no-clobber) preserves any prefix-renamed meshes from
gotcha #1. If `meshdir` is unset in the compiler element, MuJoCo treats
mesh paths as relative to the model file itself — the snippet above
handles that by defaulting to `'.'`.

**Prevention going forward.** Always run the file-count check after the
attach script, before bothering with the visual viewer step. A short
combined `assets/` dir is the canary.

---

## 5. Tendon-driven hands can lose actuators

**Symptom: most hand sliders are missing.** The combined model
compiles, but `nu` is too low. For example, `so101_arm` has 5
actuators and `aero_hand_right` has 7, so the combined model should
have 12. The raw attach output had only 6: the arm's five actuators
plus one thumb joint actuator. The six tendon actuators were missing.

**Cause.**

1. **Tendon actuator preservation is incomplete.** `MjSpec.attach`
   can preserve the eef bodies, joints, equality constraints, and some
   actuator defaults while dropping or partially serializing tendon
   structures, tendon position actuators, and sensors. Aero exposes
   most of its controls as `<position tendon="...">`, not direct joint
   actuators.
2. **Prefix rewrites must cover tendon route attributes.** When
   restoring a prefixed `<tendon>` block manually, `name`, `site`,
   `geom`, `joint`, and `tendon` are not enough. Tendon route
   `<geom ... sidesite="..."/>` references must be prefixed too.

**Detection.**

Compare source and combined model counts:

```bash
./.venv/bin/python -c "
import mujoco
for p in [
  'robots/<arm>/<arm>.xml',
  'robots/<eef>/<eef>.xml',
  'robots/<arm>_<eef>/<arm>_<eef>.xml',
]:
    m = mujoco.MjModel.from_xml_path(p)
    print(p, 'nq=', m.nq, 'nu=', m.nu, 'ntendon=', m.ntendon,
          'neq=', m.neq, 'nsensor=', m.nsensor)
    print('  actuators:', [m.actuator(i).name for i in range(m.nu)])
"
```

If `combined.nu != arm.nu + eef.nu`, inspect the source eef:

```bash
grep -n '<tendon\|<actuator\|<sensor\|tendon=' robots/<eef>/<eef>.xml
```

**Fix: restore tendon blocks and tendon actuators.**

For Aero-style hands, copy the eef's `<tendon>` and `<sensor>` blocks
into the combined XML with the same prefix used during attach, and add
back the missing tendon actuators. Prefix these attributes inside the
copied blocks: `name`, `class`, `site`, `geom`, `sidesite`, `joint`,
and `tendon`.

The corresponding compile check after repair should show the expected
actuator and tendon counts. For `so101_arm + aero_hand_right`:

```text
combined nq=21 nu=12 nbody=29 ntendon=20 neq=5
actuators= shoulder_pan, shoulder_lift, elbow_flex, wrist_flex,
           wrist_roll, aero_right_index_A_tendon, ...
```

**Prevention going forward.** Treat any eef with `<tendon>` or
`<position tendon="...">` as a special case. Before declaring the
model done:

- compare `nu`, `ntendon`, `neq`, and `nsensor` against the source
  arm/eef counts;
- inspect viewer sliders for missing tendon controls;
- verify every copied tendon route has prefixed `sidesite` references.

---

## 6. MuJoCo version

`MjSpec.attach()` requires MuJoCo Python ≥ 3.5. Versions 3.4.x have a
name-decoding bug that surfaces as garbled body names in the combined
output. We hit this and upgraded `robot_sim_env/` to mujoco 3.8.0.

```bash
./.venv/bin/python -c 'import mujoco; print(mujoco.__version__)'
# Should be >= 3.5.0
```

If older: `./robot_sim_env/bin/pip install -U "mujoco>=3.5"`.
