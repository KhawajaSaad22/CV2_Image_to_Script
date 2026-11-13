# Workbench improvement roadmap

Reviewed 13 November 2026 against the code and Git history. This is a proposal;
the documentation update does not install libraries or implement these features.
The existing 60-test suite passed during this review.

## First priority: make the current workflow clearer

| Current observation | Proposed change | Acceptance check |
|---|---|---|
| Several equally prominent toolbar actions plus a second generation row | Group Open/Save, Preview, Export and Dataset actions; move secondary commands into menus | Core workflow is clear at 1280x720 and with keyboard navigation |
| Random rules are edited in `QPlainTextEdit` as JSON | Native controls for Fixed / Uniform range / Discrete choices, probability and valid odd kernels; retain an Advanced JSON view | UI and JSON round-trip to the same validated recipe |
| `Canvas.show_array()` always calls `fit()` | Preserve zoom/pan for parameter changes; add linked views, explicit Fit and 100% actions | Refreshing settings does not move the inspected location; geometry changes have a defined reset policy |
| Exact PNG save and replay run synchronously | Worker jobs with visible progress, job state and immutable input/recipe snapshots | UI stays responsive and saved output matches the initiating recipe |
| Pipeline list uses Up/Down and raw operation keys | Searchable categorized operations, readable names, drag/drop order and contextual help | Order, enabled state and undo/redo remain correct |
| No saved-state marker in `Document` | Dirty-state tracking, save/discard prompt, recent recipes and autosave recovery | Closing/reopening cannot silently discard unsaved work |
| Styling mixes a palette with hard-coded 12px rules | Centralize spacing/font/theme tokens; test high DPI and light/dark modes | Labels, focus and controls remain legible at supported scaling factors |

Prefer PySide6's existing `QAction`, menus, toolbars, layouts, `QSettings` and worker
infrastructure before introducing a new UI framework. Keep numerical preprocessing
controls visible; model/package implementation details need not appear in the main UI.

## Second priority: maintainability and reliability

- Split `workbench.py` into canvas, parameter panel, action/controller and worker
  modules. Keep `engine.py`, document state and dataset logic independent of Qt.
- Expand semicolon-compressed functions, add types at public boundaries, and apply
  a consistent formatter/linter in a separate behavior-preserving change.
- Extend the operation registry to hold labels, help, parameter widgets, random
  rules, annotation support and export requirements in one place.
- Version recipe migrations explicitly. Preserve old replay semantics; never silently
  reinterpret a historical transform. Maintain old-recipe fixtures in CI.
- Define an asynchronous error/job state for previews, exact saves and generation.
  Cooperative cancellation occurs between OpenCV calls, not inside them.
- Use a dedicated locked development environment after Windows/Linux validation;
  record runtime versions in bundles and generated reports.
- Add clean Windows installer/update/uninstall checks and accessible focus/tab order.
  Keep actual desktop tests distinct from offscreen widget tests.

The main compatibility contract is unchanged: exported fixed scripts and generation
bundles run independently of Qt. Optional libraries must not silently become required
by an export that claims to need only NumPy/OpenCV.

## Useful additions after the cleanup

1. Before/after swipe and blink comparison, overlay opacity and a difference view.
2. Channel histograms and ROI statistics, clearly distinguishing preview pixels from
   original-image coordinates. A histogram/contrast score is not a quality guarantee.
3. Interactive ROI/crop selection with coordinate round-trip checks.
4. Preset browser with thumbnails, descriptions and before/after examples.
5. Bilateral denoising, connected-component analysis and perspective correction as
   separate operations with explicit mask/box/keypoint support or rejection.
6. Batch QA: empty/near-identical outputs, clipping/saturation, blur indicators,
   sample contact sheets and downloadable quality summaries.
7. COCO and YOLO adapters with explicit class/category mapping and coordinate tests;
   importing an annotation format does not require running a YOLO model.
8. Optional video-frame sampling after the image workflow is stable. Video timing,
   cancellation and output-size limits need their own design.

## Library candidates

These are candidates to prototype, not new requirements. Prefer adding a dependency
only when it removes meaningful custom code or enables an agreed feature.

| Candidate | Appropriate use | Adoption condition |
|---|---|---|
| [superqt](https://pyapp-kit.github.io/superqt/widgets/qrangeslider/) | Labeled floating/range sliders and collapsible controls | Verify the PySide6 backend, high-DPI behavior and packaged build; native Qt is sufficient for the first redesign |
| [pyqtgraph ImageView](https://pyqtgraph.readthedocs.io/en/latest/api_reference/widgets/imageview.html) | Histograms, ROI analysis and scientific image inspection | Prototype a separate analysis panel first; do not replace a working canvas solely for styling |
| [Ruff](https://docs.astral.sh/ruff/) | Consistent formatting, imports and lint checks | Development-only; introduce a baseline and avoid mixing large formatting diffs with behavior changes |
| [Pydantic JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/) | Typed application/manifests and clearer boundary errors | Do not duplicate the existing operation registry or force an undeclared dependency into standalone exports |
| [scikit-image metrics](https://scikit-image.org/docs/stable/api/skimage.metrics.html) | Optional SSIM/PSNR and additional analysis operations | Validate dtype, channel range and interpretation; image similarity does not measure defect-detection accuracy |

License references reviewed: [superqt](https://github.com/pyapp-kit/superqt/blob/main/LICENSE),
[pyqtgraph](https://github.com/pyqtgraph/pyqtgraph/blob/master/LICENSE.txt),
[Ruff](https://github.com/astral-sh/ruff/blob/main/LICENSE), and
[scikit-image](https://github.com/scikit-image/scikit-image/blob/main/LICENSE.txt).
Check the exact packaged versions and required notices when adopting a candidate.
No paid model or hosted API is needed for the first cleanup milestones.

## Suggested implementation order

First implement guided random controls, preserve viewport state and group actions.
Next add asynchronous exact save plus dirty-state protection. Then extract UI modules
and introduce optional analysis tools. Promote completed work into
[PATCH_NOTES.md](PATCH_NOTES.md) with its commit and validation evidence.
