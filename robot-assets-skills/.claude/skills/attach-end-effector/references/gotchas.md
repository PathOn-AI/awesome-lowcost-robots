# `attach-end-effector` Gotchas

Concrete failure modes the underlying `attach_arm_end_effector.py` doesn't
handle, with the fix recipe for each. Read this before declaring an
attach "done".

---

## 1. Mesh-filename collisions silently render the wrong geometry

**Symptom.** End-effector visual looks completely wrong (wrong shape,
wrong size, often a "huge mystery box" hovering near the wrist). Model
compiles cleanly; `nq`/`nu` are as expected.

**Cause.** The script copies arm assets first, then end-effector
assets, with `if not dest_file.exists(): copy`. If both arm and
end-effector ship a STL/OBJ file with the **same filename**, the
end-effector's version is *silently dropped* and its `<mesh file=...>`
ref ends up resolving to the arm's mesh.

**Concrete example we hit.** Piper arm's `base_link.stl` (535 KB,
arm-base mesh) and allegro_right's `base_link.stl` (164 KB, palm mesh).
The combined model's `<mesh name="right_base_link" file="base_link.stl"/>`
silently rendered the piper arm-base as the allegro palm.

**Detection.** After running the script, list `assets/` files and
compare sizes:

```bash
diff <(stat -c '%n %s' robots/<arm>/assets/*) \
     <(stat -c '%n %s' robots/<arm>_<eef>/assets/*)
```

Any size mismatch on a same-named file is the bug.

**Fix.** Handle every collision in one pass — the `base_link.stl` case
above is just one instance of a general problem (any same-named mesh
between arm and eef). For each colliding file, copy the eef's version
into the combined `assets/` under a prefixed filename and rewrite the
matching `<mesh ... file="...">` ref in the combined XML.

```bash
# Inputs — adjust to your run
PREFIX="<prefix>_"           # e.g. "right_" — must match the --prefix passed to the script
ARM_EEF=<arm>_<eef>          # e.g. piper_arm_allegro_right
EEF_XML=robots/<eef>/<eef>.xml

# Resolve eef meshdir (same recipe as §4 / workflow Fix 1)
EEF_MESHDIR=$(./.venv/bin/python -c "
import xml.etree.ElementTree as ET, pathlib
xml = pathlib.Path('$EEF_XML')
comp = ET.parse(xml).getroot().find('compiler')
md = (comp.get('meshdir') if comp is not None else None) or '.'
print((xml.parent / md).resolve())
")

PREFIX="$PREFIX" EEF_MESHDIR="$EEF_MESHDIR" ARM_EEF="$ARM_EEF" \
./.venv/bin/python - <<'PYEOF'
import os, re, shutil
from pathlib import Path

prefix = os.environ['PREFIX']
eef = Path(os.environ['EEF_MESHDIR'])
combined = Path('robots') / os.environ['ARM_EEF']
assets = combined / 'assets'
xml_path = combined / (combined.name + '.xml')

text = xml_path.read_text()
collisions = [f for f in eef.iterdir()
              if (assets / f.name).exists()
              and (assets / f.name).stat().st_size != f.stat().st_size]

for f in collisions:
    new_name = f"{prefix}{f.name}"
    shutil.copy(f, assets / new_name)
    pat = re.compile(rf'(<mesh\b[^/>]*\bfile=")({re.escape(f.name)})(")')
    text, n = pat.subn(rf'\1{new_name}\3', text)
    print(f"  {f.name}  ->  {new_name}   ({n} ref(s) updated)")

xml_path.write_text(text)
print(f"Resolved {len(collisions)} collision(s)")
PYEOF
```

Reload in viewer to confirm the correct meshes render. If `Resolved 0
collision(s)` prints, you're clean — no rewrite happened. Re-run the
detection diff above to confirm the merged `assets/` is consistent.

**Prevention going forward.** Any time arm and end-effector both ship a
mesh whose basename appears in both `assets/` dirs, plan the rename
ahead of time (do step 1+2 *before* step 5 of the workflow).

---

## 2. End-effector root body origin on the wrong face for wrist mounting

**Symptom.** End-effector visually mounts at the wrist but the palm
body extends *into the arm* (i.e. the back of the palm is hidden inside
link6). Fingers project from the wrist origin, palm geometry is behind
them sticking into the arm.

**Cause.** Some standalone MJCFs (notably mujoco_menagerie's wonik_allegro
left_hand.xml / right_hand.xml) place the palm body's *origin* at the
**front face** of the palm — where the fingers attach — with the palm
geometry extending in palm-local -Z direction. With identity quat at
the wrist flange (the script's default after attach), this puts the
back of the palm at wrist Z = -palm_depth = ~5–10 cm into the arm.

**Detection.** Run the bundled helper on the standalone eef MJCF — it
compiles the model, finds the worldbody root, and computes the
negative-Z extent of every collision geom in body-local frame:

```bash
./.venv/bin/python .claude/skills/attach-end-effector/scripts/compute_wrist_offset.py \
    robots/<eef>/<eef>.xml
```

If `H (collision-flush, recommended) > 0`, this gotcha applies. If
`H = 0`, the root origin already sits at the back of the palm — no
offset needed. (Visual: opening the combined `scene.xml` in
`mujoco.viewer` and seeing eef body clip through the wrist is the same
diagnosis, but the helper gives you the exact H to apply.)

The helper reports two values:
- `H (collision-flush)` — uses only collision geoms (`contype |
  conaffinity != 0`). Recommended: contact volumes sit flush with the
  wrist flange.
- `H (visual + collision union)` — includes visual meshes. Usually
  larger because real eef hardware extends behind the palm origin
  (cables, mounting plate). Don't use this — it pushes the eef forward,
  leaving a contact gap at the wrist.

**Fix.** Add `pos="0 0 H"` to the prefixed root body in the combined
XML, using the collision-flush H from the helper. The quat stays
identity unless there's a separate orientation issue.

```bash
# Before
<body name="<prefix>_palm" childclass="..." quat="0 0.707107 0 0.707107">
# After (use the H printed by compute_wrist_offset.py)
<body name="<prefix>_palm" childclass="..." pos="0 0 <H>" quat="1 0 0 0">
```

**Prevention.** Run `compute_wrist_offset.py` in the preflight step
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

## 5. MuJoCo version

`MjSpec.attach()` requires MuJoCo Python ≥ 3.5. Versions 3.4.x have a
name-decoding bug that surfaces as garbled body names in the combined
output. We hit this and upgraded `robot_sim_env/` to mujoco 3.8.0.

```bash
./.venv/bin/python -c 'import mujoco; print(mujoco.__version__)'
# Should be >= 3.5.0
```

If older: `./robot_sim_env/bin/pip install -U "mujoco>=3.5"`.
