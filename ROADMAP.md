# CV2 Image to Script roadmap

Updated 16 November 2026. This is the current delivery plan. Completed features
are distinguished from proposals; dates below describe delivered patches, not
promised release deadlines. Detailed history lives in [PATCH_NOTES.md](PATCH_NOTES.md).

## Delivered foundation

| Area | Current behavior |
|---|---|
| Pipeline editing | Validated operations, ordering, enable/disable, duplication, undo/redo and guided random settings |
| Inspection | Fast/Exact previews, intermediate stages, pixel readout, preserved viewport, linked zoom/pan, Fit, 100% and absolute differences |
| Saving and recovery | Background exact PNG save, saved-state marker, Save/Discard/Cancel protection, atomic recipe writes and per-window recovery snapshots |
| Export | Independent NumPy/OpenCV fixed scripts and reproducible paired dataset-generation bundles |
| Optional GPU | Supported CUDA preprocessing with explicit CPU fallback and execution metadata; default packaging remains CPU-compatible |
| Packaging | Windows portable application/installer and Linux container checks |
| Code organization | Separate canvas, comparison, document/export and recovery modules |

The 16 November recovery patch debounces snapshots by one second. Recovery is
explicit through File → Recover autosaved recipe, not automatic replacement of
the current document. Snapshots contain recipe settings and optional recipe path,
not images, image galleries, undo history or GPU state. They are not a guarantee
against edits lost before the timer fires, failed writes or disk/power failure.

## Next milestone: navigation and recovery usability

Priority: high. Status: planned.

- Recent recipes with missing-file diagnostics and bounded history.
- A recovery browser showing original recipe name, saved time and validation
  status, with explicit preview/restore/delete actions.
- Clearly distinguish snapshots belonging to open windows before adding automated
  cleanup or retention. Never delete another window's working snapshot silently.
- Searchable operation list with readable labels and categories.
- Drag/drop ordering that preserves step IDs, selected settings, random rules and
  undo/redo behavior.

Acceptance: cancelled/failed opens preserve the current recipe; missing and malformed
files produce useful messages; moving a step keeps its identity and sampled rules;
recovery deletion requires an explicit user action and affects only the selected entry.

## Next milestone: responsive long-running work

Priority: high. Status: planned.

- Background replay with immutable inputs and visible progress/cancellation.
- A consistent job-state display for preview, replay, exact save and dataset generation.
- Isolate parameter-panel and job-controller code from the main window.
- Measure large-image comparison latency and memory before introducing asynchronous
  difference rendering or additional intermediate copies.

Acceptance: stale job results never replace current work; cancellation does not label
partial output complete; closing does not abandon a queued exact save; jobs retain
the image/recipe snapshot from when they started.

## Later milestone: richer visual inspection

Priority: medium. Status: planned.

- Before/after swipe and blink, optional overlays and accessible comparison controls.
- ROI selection, channel histograms and pixel statistics.
- Explicit original-image versus Fast-preview coordinates for interactive crop/ROI.
- Keyboard navigation, high-DPI layout checks and a consistent spacing/theme system.

Acceptance: crop coordinates round-trip correctly; overlays do not change export
pixels; different-sized images are not silently treated as registered; comparisons
remain display tools rather than model-accuracy or image-quality claims.

## Later milestone: dataset quality and interoperability

Priority: medium. Status: planned.

- Batch QA for duplicates, empty outputs, clipping and blur indicators, with retained
  manifests and contact sheets.
- Reviewed COCO/other annotation adapters with class mapping and coordinate tests.
- Additional operations only with explicit paired-mask/box/keypoint support or clear
  rejection when the transform is unsupported.
- Larger synthetic fixtures and real-data evaluation after suitable data is supplied.

Acceptance: source grouping is preserved across train/validation/test; segmentation
class IDs and image geometry stay consistent; duplicate/quality warnings do not
pretend to establish label correctness or real detector performance.

## Later milestone: measured performance and distribution

Priority: medium. Status: planned.

- Benchmark real mixed CPU/CUDA recipes, including transfers and intermediate previews.
- Prototype more CUDA operations and persistent device buffers only after identifying
  a measured bottleneck; retain explicit fallback and parity checks.
- Lock validated deployment dependencies and retain third-party notices.
- Broaden packaged-app launch, installer update/uninstall and Linux runtime checks.
- Record reproducible performance inputs, source versions and measurement scope.

Acceptance: speed comparisons use the same recipe/input with numerical checks;
default CPU installation remains usable; exported fixed scripts stay independent of
Qt and optional model libraries; no generic real-time or storage-saving guarantee.

## Working order and verification

Implement navigation/recovery usability and responsive jobs first, then richer
inspection and dataset tooling. Keep formatting-only cleanup separate from behavior
changes. Prefer existing Qt, OpenCV, NumPy and standard-library capabilities; add a
library only after a focused prototype demonstrates a benefit.

Each delivered patch updates the README and patch notes, runs appropriate regression
checks, and verifies changed GUI flows. Windows packaging and Linux CI remain release
checks. CUDA-specific tests need an actual CUDA environment and may be explicitly
skipped in CPU CI; a passing CPU build does not validate GPU execution.
