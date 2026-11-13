# Patch notes

Last reviewed: 13 November 2026.

Completed entries below are reconstructed from the repository's commits and current
implementation. Commit dates are shown as Europe/Berlin calendar dates. These are
development patches, not invented semantic-version releases or release tags.
Future items are proposals and are not included in the current application.

## Current documentation update — 13 November 2026

- Added this commit-linked history and a prioritized [roadmap](ROADMAP.md).
- Reviewed interface clarity, code organization and candidate libraries.
- Reran the existing workbench suite: 60 tests passed. No runtime code, dependency
  installation, UI redesign or exported-script behavior changed in this update.

## Completed patches

### 13 November 2026 — Optional CUDA preprocessing

[GPU implementation](https://github.com/KhawajaSaad22/CV2_Image_to_Script/commit/0e06f435ad384318da55a6b90947346635e88cfc) · [CPU cache compatibility fix](https://github.com/KhawajaSaad22/CV2_Image_to_Script/commit/b42d079a35352c8f2a33243f2aa9839689a245b7)

- Added Auto / CPU / CUDA preview and exact-save selection, execution metadata and a dedicated GPU CLI.
- Added CUDA crop, flip, brightness/contrast, gamma, nearest resize and grayscale fixed threshold; other operations explicitly fall back to CPU or fail in strict mode.
- Kept standalone exports and dataset generation on the independent CPU engine.
- Added optional PyTorch requirements and a GPU Docker target; default packaging remains CPU-compatible.
- Removed unnecessary hashing during uncached CPU execution; preserved prefix caching when Auto falls back to CPU.
- Validation: 68 workbench tests pass locally with one CUDA-only skip in the CPU environment; all four dedicated GPU/backend tests pass in the CUDA container.
- Validated CUDA operations and mixed fallback. The 2048² synthetic recipe matched CPU pixels exactly and measured 9.49 ms CUDA median versus 37.46 ms CPU, including transfers. See [GPU.md](GPU.md) for scope.
- Future work: more CUDA operations, persistent device buffers and real-image/GUI benchmarks.


### 13 November 2026 — Guided settings and responsive workbench

[Commit 39d56926](https://github.com/KhawajaSaad22/CV2_Image_to_Script/commit/39d5692692b30eabedc2737373b277cc0e8e576b)

- Added native Fixed / Range / Choices controls with a synchronized Advanced JSON
  tab. Invalid rules leave the accepted recipe unchanged; odd-kernel validation is retained.
- High-precision range rules stay in Advanced JSON instead of being silently rounded.
- Grouped file/export commands in File and generation/replay commands in Dataset,
  with a shorter primary toolbar.
- Preserved zoom/pan for same-size preview updates; image switches and changed
  output dimensions reset the view deliberately.
- Moved exact PNG saving to a background worker with copied image/recipe state.
  Closing is deferred while an exact save is pending, so queued saves are not dropped.
- Added regression coverage for guided/JSON rules, stable zoom and recipe snapshots.
- Validation: 64 workbench tests pass locally, including existing standalone export
  and dataset bundle checks. These changes use existing dependencies.
- Still pending: linked canvases, autosave/dirty-state recovery, background replay,
  drag/drop ordering and the larger module/style cleanup.

This entry is delivered with its implementation; the corresponding changes are
available through the [file history](https://github.com/KhawajaSaad22/CV2_Image_to_Script/commits/main/PATCH_NOTES.md).

### 12 November 2026 — Sampled process-memory profiling

[Commit ffe654dd](https://github.com/KhawajaSaad22/CV2_Image_to_Script/commit/ffe654ddcac0d99a42efc289bac102a064cac58a)

- Added psutil-based baseline and sampled peak process RSS to the profiling tool.
- Kept warm CPU latency measurements and recorded the 10 ms sampling limitation.
- Added a subprocess regression check for memory and timing report fields.
- GPU memory and guaranteed capture of short-lived peaks are not measured.

### 11 November 2026 — Personal documentation perspective

[Commit 06bd63ad](https://github.com/KhawajaSaad22/CV2_Image_to_Script/commit/06bd63ad81d788fbe4e66435dd3abe5cc8cc02df)

- Updated README wording to describe my files, configuration and pipeline from my
  perspective. This patch changed documentation only.

### 10 November 2026 — Rotation correctness and clearer generation behavior

[Commit 4dae6016](https://github.com/KhawajaSaad22/CV2_Image_to_Script/commit/4dae601649decd6f4344cf41bcc05e4f12ad1441)

- Added an expanding rotation canvas and exact quarter-turn handling; intentional
  clipping remains available through the keep-canvas setting.
- Preserved historical replay geometry while migrating older editable recipes.
- Updated paired mask/box/keypoint rotation handling and regression tests.
- Added operation descriptions, parameter help and OpenCV implementation references.
- Exposed active randomization rules, fixed-setting warnings, seed guidance and
  generated duplicate counts. Did not promise unique outputs for every variant.

### 10 November 2026 — Paired-generation example and build scheduling

[Commit d53bd448](https://github.com/KhawajaSaad22/CV2_Image_to_Script/commit/d53bd448b47bb1de60d542fce9fc8b9e24eecdde)

- Added a runnable paired-target dataset example and documented its generation/replay.
- Configured newer workflow runs to cancel superseded builds on the same ref.

### 10 November 2026 — Reproducible dataset generation and Windows packaging

[Commit 069aede5](https://github.com/KhawajaSaad22/CV2_Image_to_Script/commit/069aede51a24399b2045ccd33e40396762e5d8de)

- Added seeded parameter/probability sampling, contact sheets and random recipe UI.
- Added generation manifests, replay records, progress and cooperative cancellation.
- Added paired transformations for class-ID masks, boxes and keypoints, with
  split/content checks and documented coordinate conventions.
- Added portable dataset-generation bundles and replay commands.
- Added Windows portable-application and installer configuration, packaged-runtime
  checks and CPU profiling. Later patches expanded profiling and rotation behavior.

### 10 November 2026 — Qt test cleanup and Linux font dependencies

[Commit 589ba725](https://github.com/KhawajaSaad22/CV2_Image_to_Script/commit/589ba725339c77b8df64e7093334d60e99914301)

- Improved Qt test-window teardown and added Linux font/runtime dependencies.
- This was a test/runtime compatibility patch, not a new image-processing feature.

### 10 November 2026 — Desktop pipeline workbench

[Commit 6346e8ee](https://github.com/KhawajaSaad22/CV2_Image_to_Script/commit/6346e8eeef4be81be72b5db04472b9595a5026f0)

- Introduced the PySide6 workbench, representative-image gallery, ordered operations,
  parameter controls, before/after canvases and intermediate-stage inspection.
- Added fast/exact preview modes, background preview processing, configuration
  undo/redo, versioned recipes, PNG output and standalone Python export.
- Added the processing engine, sample pipeline, tests, Dockerfile and build workflow.
- Kept the earlier PyQt5 prototype separate from the new runtime.

### 29 March 2025 — Legacy prototype editing guards and history

[Commit 5c9ff96c](https://github.com/KhawajaSaad22/CV2_Image_to_Script/commit/5c9ff96c2b3d49e961d2d5b3125cad29a444487e)

- Expanded the original prototype with image-dependent preview checks, filter
  preparation, layer visibility and image-based undo/redo behavior.
- These historical controls belong to `cv2_image_app.py`; current workbench history
  stores pipeline configuration rather than copies of image pixels.

### 28 March 2025 — Explicit Apply Filter action

[Commit 61a8285c](https://github.com/KhawajaSaad22/CV2_Image_to_Script/commit/61a8285c9fdc41c5adc5a4af0f0a46f2df746d4f)

- Separated temporary filter preview from explicitly applying a filter in the
  original prototype, with filter/layer state and updated controls.

### 28 March 2025 — Adjustable filter controls

[Commit 2c6abf0e](https://github.com/KhawajaSaad22/CV2_Image_to_Script/commit/2c6abf0e7a18427d3b331c57f33a63bf6abc9178)

- Added sliders and parameter tracking for adjustable filters in the prototype.

### 28 March 2025 — First application prototype

[Commit 7bf417f4](https://github.com/KhawajaSaad22/CV2_Image_to_Script/commit/7bf417f432a129e7160e8ed5bd794016732d9218)

- Added the initial PyQt5/OpenCV editor with image loading, original/processed
  views, basic filters and script-export foundations.

### 28 March 2025 — Repository setup

[Commit 572502e1](https://github.com/KhawajaSaad22/CV2_Image_to_Script/commit/572502e11aa63c41e9c9bf6276748324cf3a1598)

- Created the README and Apache-2.0 license for the image-to-script project.

## Proposed future patches — not implemented

| Order | Proposed patch | Intended outcome | Completion check |
|---|---|---|---|
| 1 | Clearer workflow and navigation | Group actions; replace raw random-settings JSON with guided controls and an advanced editor | Keyboard-only and small-window workflows remain usable |
| 2 | Stable viewing and responsive saving | Preserve zoom/pan, add linked views, move exact save/replay off the UI thread | Refresh does not reset the view; save uses an immutable recipe snapshot |
| 3 | Safe editing and reusable recipes | Dirty-state prompts, autosave recovery, named presets, drag/drop ordering | Recovery preserves the recipe; reordering still produces the correct export |
| 4 | Code and schema cleanup | Smaller UI modules, readable formatting, shared operation definitions and migrations | Existing recipes, bundles and standalone exports remain compatible |
| 5 | Analysis and dataset tools | Histograms, differences/overlays, ROI tools and selected new operations | Label geometry and dtype/color behavior have explicit tests |
| 6 | Optional adapters and distribution | COCO/YOLO import/export, selected library backends, published tested containers | Coordinate round trips and exported dependencies are documented and tested |

No delivery dates are committed. See [ROADMAP.md](ROADMAP.md) for scope, dependency
options and acceptance checks. New completed entries should identify a commit and
validation evidence; moving a plan into this history requires implementation.
