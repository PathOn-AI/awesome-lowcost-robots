# AGENTS.md

Skill bundle for coding agents (Claude Code, Codex, etc.) working with
robot URDF/MJCF assets — attaching end-effectors, converting between
URDF and MJCF, and the post-processing fixups the underlying scripts
don't handle.

## Skill routing

Use the bundled skills for workflow details:

- `.claude/skills/attach-end-effector/SKILL.md` — mount a gripper, dex
  hand, or tool on a robot arm via MuJoCo's MjSpec API. Use when
  combining an arm MJCF and an end-effector MJCF into a single
  `robots/<arm>_<eef>/` model.
- `.claude/skills/urdf-to-mjcf/SKILL.md` — convert a URDF to MJCF and
  post-tune the result (mimics → `<equality>`, inertias, contact
  excludes, position actuators). Always check `mujoco_menagerie` first.
- `.claude/skills/mjcf-to-urdf/SKILL.md` — reverse direction for
  pinocchio/RViz/MoveIt consumers. Lossy: equality constraints,
  actuators, contact excludes all drop. Use only when the consumer
  doesn't accept MJCF and a hand-maintained URDF doesn't already exist.

When asked to *combine* an arm and end-effector, route to
`attach-end-effector`. When asked to *bring a URDF into MuJoCo*, route
to `urdf-to-mjcf`. When asked to *export an MJCF for an external
URDF-only consumer*, route to `mjcf-to-urdf`.

`AGENTS.md` is intentionally bundle-focused. Reusable workflow rules
and gotchas live inside each skill's `references/`.

## Python environment

Use the bundle-local venv:

```bash
./.venv/bin/python
```

Bootstrap if missing or broken:

```bash
cd robot-assets-skills/
python3 -m venv .venv
for s in attach-end-effector urdf-to-mjcf mjcf-to-urdf; do
    ./.venv/bin/pip install -r .claude/skills/$s/requirements.txt
done
```

Each skill owns its `requirements.txt`. The shared `.venv/` works for
all three planned skills (they all need `mujoco>=3.5`); add per-skill
deps as new skills are scaffolded. If a future skill needs deps that
conflict with the shared venv (e.g. ROS), it should declare its own
env in its `SKILL.md` and explicitly say "do not install into the
shared `.venv`".

## Bundle conventions

- **`robots/` is user-populated, with two example inputs shipped.**
  `robots/piper_arm/` and `robots/allegro_right/` are tracked in git as
  ready-to-use example inputs. Everything else under `robots/` is
  gitignored — generated combined-model folders, and any extra
  arm/end-effector folders users drop in. See `README.md`
  "First-time setup".
- **Folder name == MJCF name.** `piper_arm/` contains `piper_arm.xml`.
  Skills assume this; don't rename one without the other.
- **`<site name="attachment_site"/>` on the arm.** Arms expose this
  site at the wrist flange. End-effectors mount at this site via the
  `attach-end-effector` skill.
- **Combined models are MJCF-only.** Combined `<arm>_<eef>/` folders
  generally don't ship a URDF.
- **Headless display:** if running on a headless box, set `DISPLAY`
  to your X session (e.g. a VNC display) in your shell before running
  viewer commands. Skill examples assume `$DISPLAY` is already set.

## Source of truth

- The wrapped Python scripts (e.g. `attach_arm_end_effector.py`) are
  authoritative. Skills add a workflow + gotcha layer; they don't
  replace the script.
- Prefer hand-tuned upstream MJCFs (e.g. `mujoco_menagerie`) over
  running an auto-converter when an upstream MJCF exists.

## Repo policies

- Never commit `.venv/` or generated/user-added folders under
  `robots/` from this bundle. Only the two example inputs
  (`robots/piper_arm/`, `robots/allegro_right/`) are tracked; see
  `.gitignore`.
- Combined `.mjb` binary caches are typically 50–80 MB; current policy
  is to commit them when the combined model is registered as a
  released robot, but they're not required at the bundle level.
- Edit source files; never hand-edit generated combined models when
  you can re-run the skill instead. (Exception: the post-attach fixups
  documented in `gotchas.md` are *expected* hand edits.)
