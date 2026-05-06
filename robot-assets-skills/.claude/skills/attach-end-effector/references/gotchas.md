# `attach-end-effector` Gotchas

Concrete failure modes the underlying `attach_arm_gripper.py` doesn't
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

**Fix.**

1. Copy the end-effector's version with a prefixed name into the
   combined `assets/`:
   ```bash
   cp robots/<eef>/assets/base_link.stl \
      robots/<arm>_<eef>/assets/<prefix>_base_link.stl
   ```
2. Update the combined XML's `<mesh file=...>` ref to point at the
   renamed file:
   ```bash
   sed -i 's|<mesh name="<prefix>_base_link" file="base_link.stl"/>|<mesh name="<prefix>_base_link" file="<prefix>_base_link.stl"/>|' \
       robots/<arm>_<eef>/<arm>_<eef>.xml
   ```
3. Reload in viewer to confirm the correct mesh.

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

**Detection.** Visual: open scene in MuJoCo viewer. If the eef body
clips through the wrist, this is it.

You can also check the standalone MJCF's worldbody root body for
collision boxes at z<0:

```bash
grep -A1 '<body name="palm"' robots/<eef>/<eef>.xml | head -5
grep '<geom .*pos="[^"]*-' robots/<eef>/<eef>.xml | head -5
```

**Fix.** Add a `pos="0 0 H"` to the prefixed root body in the combined
XML, where H is the palm's depth (negative-Z extent of the standalone
collision/visual). For menagerie allegro, H ≈ 0.095 m. The quat stays
identity unless there's a separate orientation issue.

```bash
# Before
<body name="<prefix>_palm" childclass="..." quat="0 0.707107 0 0.707107">
# After
<body name="<prefix>_palm" childclass="..." pos="0 0 0.095" quat="1 0 0 0">
```

**Hand-specific values seen so far.**

| End-effector | Pos offset | Notes |
|---|---|---|
| `barrett_hand` | none (no offset needed) | Internal `bh_palm` body has its origin at the back face; identity quat works. |
| `allegro_left` (menagerie) | `pos="0 0 0.095"` | Origin at front face. Palm body at `quat="0 1 0 1"` standalone needs override to `quat="1 0 0 0"`. |
| `allegro_right` (menagerie) | `pos="0 0 0.095"` | Same as left. |

**Prevention.** Inspect the standalone MJCF's first worldbody body
*before* attaching: if its collision/visual boxes are at z<0 in palm
frame, plan the pos offset.

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

| Combined | Prefix | Reason for non-empty |
|---|---|---|
| `piper_arm_barrett` | `"barrett_"` | Bare nested `<default>` in barrett source |
| `piper_arm_allegro_right` | `"right_"` | `base_link` mesh name collides |
| `piper_arm_allegro_left` | `"left_"` | Same as right |

---

## 4. End-effector meshes are not always under `assets/`

**Symptom.** Combined model fails to load with
`Error: could not open file 'assets/<some-mesh>.obj'`. The combined
`assets/` dir is missing the end-effector's mesh files entirely. The
script's stdout shows only the arm's mesh-copy line — no count for the
gripper.

**Cause.** `attach_arm_gripper.py` hard-codes the gripper's mesh source
as `gripper_path.parent / "assets"` (around line 103). End-effectors
whose `<compiler meshdir="..."/>` points anywhere else (e.g. `meshes`,
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
