# robot-assets-skills

Claude-Code skill bundle for working with robot URDF/MJCF assets:
attaching end-effectors, converting between URDF and MJCF, and the
post-processing fixups the underlying scripts don't handle.

## Skills

| Skill | Status | Slash command | Purpose |
|---|---|---|---|
| `attach-end-effector` | ready | `/attach-end-effector` | Mount a gripper / dex hand / tool on a robot arm via MuJoCo's MjSpec API. |
| `urdf-to-mjcf` | ready | `/urdf-to-mjcf` | Convert URDF→MJCF and post-tune (mimics → `<equality>`, inertias, contact excludes, position actuators). Always check `mujoco_menagerie` first. |
| `mjcf-to-urdf` | ready | `/mjcf-to-urdf` | Convert MJCF→URDF for pinocchio/RViz consumers. Lossy — equality, actuators, contact excludes all dropped. |

See `pathonai_robot_assets/docs/SKILLS_PLAN.md` for the full plan.

## Directory structure

```
robot-assets-skills/
├── README.md                              ← this file
├── AGENTS.md                              ← skill routing + Python env
├── CLAUDE.md                              ← points at AGENTS.md
├── .gitignore                             ← ignores .venv/ and robots/* (except the two example inputs below)
├── .venv/                                 ← bundle-local venv (bootstrap below)
├── .claude/skills/                        ← skill definitions
│   ├── attach-end-effector/
│   │   ├── SKILL.md
│   │   ├── requirements.txt
│   │   └── references/{workflow,gotchas}.md
│   ├── urdf-to-mjcf/
│   │   ├── SKILL.md
│   │   ├── requirements.txt
│   │   └── references/{workflow,gotchas}.md
│   └── mjcf-to-urdf/
│       ├── SKILL.md
│       ├── requirements.txt
│       └── references/{workflow,gotchas}.md
└── robots/                                ← user-populated; two example inputs ship with the bundle
    ├── piper_arm/                         ← example arm input (tracked)
    │   ├── piper_arm.xml                  MJCF — has <site name="attachment_site"/> at the wrist
    │   ├── piper_arm.urdf                 URDF — optional, for RViz/pinocchio
    │   ├── assets/                        STL meshes referenced by the MJCF
    │   └── meshes/                        STL meshes referenced by the URDF
    ├── allegro_right/                     ← example end-effector input (tracked)
    │   ├── allegro_right.xml              MJCF — required
    │   ├── allegro_right.urdf             URDF — optional
    │   ├── assets/                        STL meshes (matches <compiler meshdir="assets">)
    │   └── meshes/                        STL meshes referenced by the URDF
    ├── <your-arm>/                        ← (optional) drop in your own arm — gitignored
    ├── <your-eef>/                        ← (optional) drop in your own end-effector — gitignored
    └── <arm>_<eef>/                       ← created by the skill — gitignored
        ├── <arm>_<eef>.xml                combined MJCF
        ├── <arm>_<eef>.mjb                binary cache (large)
        ├── scene.xml                      wraps the MJCF for viewer use
        ├── assets/                        merged meshes from arm + eef
        └── README.md                      generated description
```

### Conventions

The `attach-end-effector` skill (and the underlying script) assumes:

1. **Folder name == MJCF name.** `piper_arm/` contains `piper_arm.xml`.
2. **`<site name="attachment_site"/>` on the arm**, at the wrist
   flange, with the site's `pos` / `quat` defining the mount frame. If
   your arm doesn't have one, add it before invoking the skill.
3. **`assets/` is the default mesh dir.** If your end-effector's
   `<compiler meshdir="...">` points elsewhere (e.g. `meshes/`, or
   unset), the skill handles the post-attach copy — see
   `.claude/skills/attach-end-effector/references/gotchas.md` §4.
4. **Output folder name is `<arm>_<eef>`.** Pure convention; pass it
   via `--output`.

## First-time setup

Run once when you first clone or copy this bundle.

### 1. Bootstrap the venv

```bash
cd robot-assets-skills/
python3 -m venv .venv
for s in attach-end-effector urdf-to-mjcf mjcf-to-urdf; do
    ./.venv/bin/pip install -r .claude/skills/$s/requirements.txt
done
```

Verify:
```bash
./.venv/bin/python -c 'import mujoco; print(mujoco.__version__)'
# Expect >= 3.5
```

### 2. (Optional) populate `robots/` with your own parts

The bundle ships with two example inputs already in `robots/`:
`piper_arm/` (6-DOF arm with `attachment_site` at the wrist) and
`allegro_right/` (16-DOF dexterous hand). You can run the skills
against these straight away.

To use your own arm or end-effector instead, drop them in alongside:

```bash
cp -r /path/to/your/arm     robots/<arm-name>/
cp -r /path/to/your/eef     robots/<eef-name>/
```

Each folder must follow the structure under "Directory structure"
above (folder name matches the `.xml` name, `assets/` directory
present). User-added folders are gitignored.

Confirm the parts you'll attach compile standalone:

```bash
./.venv/bin/python -c "
import mujoco
print('arm:', mujoco.MjModel.from_xml_path('robots/<arm-name>/<arm-name>.xml').nu, 'actuators')
print('eef:', mujoco.MjModel.from_xml_path('robots/<eef-name>/<eef-name>.xml').nu, 'actuators')
"
```

### 3. Launch Claude Code from the bundle

```bash
cd robot-assets-skills/
claude
```

The bundle's `.claude/skills/` is auto-discovered. Verify with the
slash-command autocomplete (type `/` and look for
`attach-end-effector`).

## Usage

Once setup is done:

```
/attach-end-effector mount <eef-name> on <arm-name>
```

Or describe the task naturally — the agent reads the skill's frontmatter
`description:` and auto-invokes when it matches. Example:

> "Combine piper_arm with allegro_right into a piper_arm_allegro_right
>  model."

The skill walks through the workflow in
`.claude/skills/attach-end-effector/references/workflow.md` and
post-processes around the four known failure modes documented in
`.claude/skills/attach-end-effector/references/gotchas.md`.

## What the skill doesn't do

- Generate the URDFs/MJCFs themselves (use `urdf-to-mjcf` when ready).
- Verify the *physical* correctness of the combined model (inertias,
  joint limits, friction). The skill flags only the *kinematic* and
  *asset-bookkeeping* issues that compile-cleanly-but-look-wrong.
- Drive simulation. It produces the model; you bring the controller.
