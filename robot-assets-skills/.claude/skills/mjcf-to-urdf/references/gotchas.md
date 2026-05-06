# `mjcf-to-urdf` Gotchas

What gets dropped in the conversion, and how to handle each loss.

URDF is a strict subset of what MJCF can express. The conversion is
**lossy by definition** — these aren't bugs in the converter, they're
limits of the URDF spec. Each loss has a different impact depending
on what the consumer does with the URDF.

---

## 1. `<equality>` constraints are dropped

**What's lost.** Any joint coupling expressed as
`<equality><joint .../>` with a `polycoef` becomes nothing — both
joints become independent in the URDF.

**Impact.**
- *RViz / pure visualization:* low — sliders behave independently,
  but the model still renders. Just won't look mechanically coupled.
- *Pinocchio / FK / IK:* medium — IK produces solutions that are
  unreachable on the real hardware (since the hardware has the
  coupling).
- *Dynamics simulation:* high — physics is wrong.

**Workaround.** If the consumer supports URDF `<mimic>`, hand-edit the
generated URDF to add `<mimic>` clauses on the should-be-driven joints:

```xml
<joint name="<dependent>" type="revolute">
  <mimic joint="<primary>" multiplier="<k>" offset="0"/>
  ...
</joint>
```

`<mimic>` is the URDF-side equivalent of the polycoef linear case
(`joint = multiplier * primary + offset`). Polynomial polycoefs (`c2`,
`c3`, `c4` non-zero) have no URDF equivalent — those are dropped
permanently.

---

## 2. Actuators are dropped

**What's lost.** The MJCF's `<actuator>` block (positions, motors,
velocities, kp/kv tuning) doesn't appear in URDF — URDF has no
actuator concept.

**Impact.** The URDF kinematic tree exists, but there's no concept of
"controlled" vs "free" joints. Downstream consumers must:
- Decide which joints to control themselves (e.g. via a YAML config
  for MoveIt).
- Re-tune any kp/kv equivalents in their own controller.

**Workaround.** If the consumer needs to know which joints were
actuated, document them in a sidecar (e.g. `actuators.yaml`):

```yaml
controlled_joints:
  - name: <joint-name>
    actuator: position
    ctrlrange: [<min>, <max>]
    kp: <value>
    kv: <value>
```

---

## 3. Contact excludes don't survive

**What's lost.** `<contact><exclude>` entries (the "these two links
shouldn't collide even though they geometrically overlap" hints) are
not representable in URDF.

**Impact.**
- *RViz:* low — RViz doesn't do collision checking. No visible
  effect.
- *MoveIt collision checking:* medium — MoveIt may flag normally-OK
  rest-pose configurations as in collision. MoveIt has its own
  `disable_collisions` mechanism in the SRDF that can reproduce the
  exclusions, but it's a separate file.
- *Physics simulation from URDF:* high — joints stick at the same
  rest-pose collisions the MJCF was built to ignore.

**Workaround.** If the consumer is MoveIt, generate the SRDF
exclusions list from the MJCF's `<contact><exclude>` block manually:

```xml
<!-- in <robot-name>.srdf -->
<disable_collisions link1="<palm>" link2="<finger-1>" reason="Adjacent"/>
```

For other consumers, document the excluded pairs in the URDF's leading
comment.

---

## 4. Keyframes are dropped

**What's lost.** Any `<keyframe>` blocks (rest-pose snapshots,
named configurations) don't appear in URDF.

**Impact.** Mostly low — keyframes are convenience features. The
robot's home position is implicit (joint values from `<joint range>`
defaults). Document any non-trivial keyframes in a sidecar if needed.

---

## 5. `<default>` classes are flattened or dropped

**What's lost.** MJCF's hierarchical `<default>` classes don't
translate to URDF — every element gets explicit attributes inline,
or the default goes away if there's no URDF analog (e.g. `kp`,
`damping` on positions).

**Impact.** The URDF tends to be more verbose than the MJCF source.
Otherwise no semantic loss for the kinematic tree.

---

## 6. Mesh path prefixes may need fixing

**Symptom.** RViz / pinocchio fails with "could not find mesh".

**Cause.** MJCF references meshes via `<compiler meshdir="...">` +
relative `<mesh file="...">`. URDF references via `package://` or
relative-to-URDF paths. The converter writes one of:
- `<mesh filename="meshdir/mesh.stl"/>` — relative to URDF, often
  works if URDF and meshes are in the same dir.
- `<mesh filename="package://<...>"/>` — only works inside ROS.
- `<mesh filename="file:///abs/path/mesh.stl"/>` — absolute, breaks
  on move.

**Fix.** Inspect the converted URDF's mesh refs and rewrite if needed.
Most common: ensure paths are relative to the URDF location:

```bash
sed -i 's|filename="package://[^/]*/|filename="|g' robots/<robot>/<robot>.urdf
sed -i 's|filename="file:///[^"]*meshes/|filename="meshes/|g' robots/<robot>/<robot>.urdf
```

Verify in RViz before declaring done.

---

## Should I even use this skill?

Quick decision tree:

- *Consumer supports MJCF natively* (mink, MuJoCo, IsaacSim, MJX): **no**, skip the conversion.
- *Hand-maintained URDF exists upstream*: **no**, use that instead.
- *Consumer is RViz for visualization only*: **yes**, the conversion is fine.
- *Consumer is pinocchio / MoveIt / ROS*: **yes**, but be ready to
  hand-edit `<mimic>`, write an SRDF, and re-tune controllers.
- *Consumer simulates dynamics from URDF*: **no**, results will be
  wrong. Either keep MJCF or hand-write the URDF.
