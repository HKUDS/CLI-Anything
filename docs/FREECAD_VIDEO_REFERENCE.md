# FreeCAD Demo Video Reference

Last updated: 2026-04-22 UTC

This file records the programmatic video artifacts built from real
`cli-anything-freecad` trajectories and real FreeCAD preview bundles.

## Curiosity V6

Source trajectory:

- `/root/preview-artifacts/20260421/freecad-curiosity-v6/trajectory.json`

Current render target:

- `/root/preview-artifacts/20260421/freecad-curiosity-v6/demo.mp4`

Final rendered artifact:

- `/root/preview-artifacts/20260421/freecad-curiosity-v6/demo.mp4`
- duration: `116.166667s`
- size: `3,011,924 bytes`

Polished split-screen re-render:

- `/root/preview-artifacts/20260422/freecad-curiosity-v6/demo-polished.mp4`
- duration: `71.416667s`
- size: `2,266,665 bytes`

Render command:

```bash
python3 /root/CLI-Anything-preview/docs/scripts/freecad_live_preview_demo.py \
  render \
  --timeline /root/preview-artifacts/20260421/freecad-curiosity-v6/trajectory.json \
  --speed 8
```

Ending showcase method:

- reuse the real final `Curiosity v6` project JSON
- add a staged ground and marker bed as extra real geometry
- generate extra real FreeCAD `preview capture` hero bundles for a sequence of
  posed translations
- append those real hero captures as a final full-screen showcase segment in the
  programmatic video

Expected showcase cache location:

- `/root/preview-artifacts/20260421/freecad-curiosity-v6/showcase/sequence.json`
- `/root/preview-artifacts/20260421/freecad-curiosity-v6/showcase/projects/`
- `/root/preview-artifacts/20260421/freecad-curiosity-v6/showcase/captures/`

Key stills:

- trajectory end:
  `/root/preview-artifacts/20260421/freecad-curiosity-v6/stills/trajectory-end.png`
- showcase start:
  `/root/preview-artifacts/20260421/freecad-curiosity-v6/stills/showcase-start.png`
- showcase mid:
  `/root/preview-artifacts/20260421/freecad-curiosity-v6/stills/showcase-mid.png`
- showcase final:
  `/root/preview-artifacts/20260421/freecad-curiosity-v6/stills/showcase-final.png`

Implementation notes:

- the main split-screen section uses the real `Curiosity v6` live session
  timeline and real copied preview bundles
- the ending showcase uses `12` extra real FreeCAD hero captures
- the showcase segment begins after the main trajectory body and is rendered as
  a full-screen ending panel
- the current render was produced with `--speed 8`, which keeps the long real
  trajectory readable without turning the video into a many-minute raw replay

Polished render command:

```bash
python3 - <<'PY'
import importlib.util
from pathlib import Path
script = Path('/root/CLI-Anything-preview/docs/scripts/freecad_live_preview_demo.py')
spec = importlib.util.spec_from_file_location('freecad_live_preview_demo', script)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(
    mod.render_video(
        Path('/root/preview-artifacts/20260421/freecad-curiosity-v6/trajectory.json'),
        output_path=Path('/root/preview-artifacts/20260422/freecad-curiosity-v6/demo-polished.mp4'),
        fps=12,
        speed=14.0,
        keep_frames=True,
    )
)
PY
```

Polished split-screen changes:

- left panel is now a designed `Agent Command Stream`, not a literal terminal
- command cards use the real captured command strings, normalized for
  readability
- the ending no longer uses sparse hero-capture blending
- the ending now uses the real combo motion sequence:
  - one full turntable rotation
  - followed by forward travel
- ending frames are pulled from `cli-anything-freecad motion render-video`
  output via:
  `/root/preview-artifacts/20260421/freecad-curiosity-v6/showcase-motion/`

Key stills for the polished render:

- early command stream:
  `/root/preview-artifacts/20260422/freecad-curiosity-v6/stills/early-command-stream.png`
- mid preview monitor:
  `/root/preview-artifacts/20260422/freecad-curiosity-v6/stills/mid-preview-monitor.png`
- showcase rotation:
  `/root/preview-artifacts/20260422/freecad-curiosity-v6/stills/showcase-rotation.png`
- showcase final drive:
  `/root/preview-artifacts/20260422/freecad-curiosity-v6/stills/showcase-final-drive.png`

Notes:

- the split-screen body of the video is still based on the real CLI trajectory
  and the real live preview session
- the ending showcase is not a screen recording; it is a composition of extra
  real FreeCAD preview captures derived from the final project state

## Curiosity V6 True Motion Showcase

Source trajectory:

- `/root/preview-artifacts/20260421/freecad-curiosity-v6/trajectory.json`

True-motion render target:

- `/root/preview-artifacts/20260422/freecad-curiosity-v6-true-motion/curiosity_true_motion.mp4`

Final rendered artifact:

- `/root/preview-artifacts/20260422/freecad-curiosity-v6-true-motion/curiosity_true_motion.mp4`
- duration: `6.0s`
- frame count: `73`
- size: `315,872 bytes`

Render command:

```bash
python3 /root/CLI-Anything-preview/docs/scripts/freecad_live_preview_demo.py \
  motion-showcase \
  --timeline /root/preview-artifacts/20260421/freecad-curiosity-v6/trajectory.json \
  --output-dir /root/preview-artifacts/20260422/freecad-curiosity-v6-true-motion \
  --fps 12
```

Method:

- reuse the real final `Curiosity v6` project JSON
- add the staged showcase ground/markers as real geometry
- generate `13` motion key poses across `6.0s`
- store those keyframes in the project `motions` collection
- invoke `cli-anything-freecad motion render-video`
- render every frame through real FreeCAD GUI capture and encode with `ffmpeg`

Artifacts:

- motion project:
  `/root/preview-artifacts/20260422/freecad-curiosity-v6-true-motion/curiosity_true_motion.json`
- motion manifest:
  `/root/preview-artifacts/20260422/freecad-curiosity-v6-true-motion/motion_manifest.json`
- frame sequence:
  `/root/preview-artifacts/20260422/freecad-curiosity-v6-true-motion/frames/sequence.json`

Key stills:

- start:
  `/root/preview-artifacts/20260422/freecad-curiosity-v6-true-motion/stills/start.png`
- mid:
  `/root/preview-artifacts/20260422/freecad-curiosity-v6-true-motion/stills/mid.png`
- final:
  `/root/preview-artifacts/20260422/freecad-curiosity-v6-true-motion/stills/final.png`

Notes:

- this showcase uses real frame-by-frame FreeCAD renders
- no blend-based or synthetic in-between motion is used
- motion is currently driven by part-placement keyframes, not native Assembly joint simulation

## Curiosity Turntable Motion

Source trajectory:

- `/root/preview-artifacts/20260421/freecad-curiosity-v6/trajectory.json`

Turntable render target:

- `/root/preview-artifacts/20260422/freecad-curiosity-v6-turntable-motion/curiosity_turntable_motion.mp4`

Final rendered artifact:

- `/root/preview-artifacts/20260422/freecad-curiosity-v6-turntable-motion/curiosity_turntable_motion.mp4`
- duration: `7.0s`
- frame count: `85`
- size: `719,298 bytes`

Render command:

```bash
python3 /root/CLI-Anything-preview/docs/scripts/freecad_live_preview_demo.py \
  motion-showcase \
  --motion-style spin \
  --timeline /root/preview-artifacts/20260421/freecad-curiosity-v6/trajectory.json \
  --output-dir /root/preview-artifacts/20260422/freecad-curiosity-v6-turntable-motion \
  --fps 12
```

Method:

- reuse the real final `Curiosity v6` project JSON
- add the staged showcase ground/markers as real geometry
- generate `19` turntable key poses across `7.0s`
- rotate the rover around its stage-centered pivot
- invoke `cli-anything-freecad motion render-video`
- render every frame through real FreeCAD GUI capture and encode with `ffmpeg`

Artifacts:

- motion project:
  `/root/preview-artifacts/20260422/freecad-curiosity-v6-turntable-motion/curiosity_turntable_motion.json`
- motion manifest:
  `/root/preview-artifacts/20260422/freecad-curiosity-v6-turntable-motion/motion_manifest.json`
- frame sequence:
  `/root/preview-artifacts/20260422/freecad-curiosity-v6-turntable-motion/frames/sequence.json`

Key stills:

- start:
  `/root/preview-artifacts/20260422/freecad-curiosity-v6-turntable-motion/stills/start.png`
- mid:
  `/root/preview-artifacts/20260422/freecad-curiosity-v6-turntable-motion/stills/mid.png`
- final:
  `/root/preview-artifacts/20260422/freecad-curiosity-v6-turntable-motion/stills/final.png`

Notes:

- this turntable is also a real frame-by-frame FreeCAD render
- no synthetic in-between frames are used
- orientation is currently driven by per-part placement keyframes, not native Assembly joint simulation

## Curiosity Combo Motion

Source trajectory:

- `/root/preview-artifacts/20260421/freecad-curiosity-v6/trajectory.json`

Combo render target:

- `/root/preview-artifacts/20260421/freecad-curiosity-v6/showcase-motion/curiosity_combo_motion.mp4`

Final rendered artifact:

- `/root/preview-artifacts/20260421/freecad-curiosity-v6/showcase-motion/curiosity_combo_motion.mp4`
- duration: `9.0s`
- frame count: `109`

Render command:

```bash
python3 /root/CLI-Anything-preview/docs/scripts/freecad_live_preview_demo.py \
  motion-showcase \
  --motion-style combo \
  --timeline /root/preview-artifacts/20260421/freecad-curiosity-v6/trajectory.json \
  --output-dir /root/preview-artifacts/20260421/freecad-curiosity-v6/showcase-motion \
  --fps 12
```

Method:

- reuse the real final `Curiosity v6` project JSON
- add the staged showcase ground/markers as real geometry
- generate `25` motion key poses across `9.0s`
- first do one full turntable rotation
- then drive forward across the stage
- render every frame through real FreeCAD GUI capture
- encode the result to MP4 with `ffmpeg`

Artifacts:

- motion project:
  `/root/preview-artifacts/20260421/freecad-curiosity-v6/showcase-motion/curiosity_combo_motion.json`
- motion manifest:
  `/root/preview-artifacts/20260421/freecad-curiosity-v6/showcase-motion/motion_manifest.json`
- frame sequence:
  `/root/preview-artifacts/20260421/freecad-curiosity-v6/showcase-motion/frames/sequence.json`

Key stills:

- start:
  `/root/preview-artifacts/20260421/freecad-curiosity-v6/showcase-motion/stills/start.png`
- mid:
  `/root/preview-artifacts/20260421/freecad-curiosity-v6/showcase-motion/stills/mid.png`
- final:
  `/root/preview-artifacts/20260421/freecad-curiosity-v6/showcase-motion/stills/final.png`
