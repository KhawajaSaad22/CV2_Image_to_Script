# CV2 Image to Script — Pipeline Workbench

A local desktop editor for building image-preprocessing pipelines, inspecting live
intermediate results, and exporting standalone OpenCV/NumPy code.

## Implemented: Phases 1–6

- Load several representative images and switch between them in a gallery.
- Add, reorder, disable, duplicate, and remove processing operations.
- Edit parameters with sliders, numeric fields, and validated choices.
- Inspect original/processed images side by side; zoom, pan, fit, and read pixel values.
- Inspect any intermediate stage, dimensions, channels, value range, and timings.
- Choose fast previews or exact full-resolution processing.
- Undo/redo pipeline configuration, including parameter changes and ordering.
- Save/reopen versioned pipeline JSON.
- Export a self-contained Python script for one image or a recursive folder batch.
- Save the exact processed image as PNG.
- Randomize parameter ranges/choices and per-operation probabilities with stable seeds.
- Inspect frozen sampled contact sheets and export a particular sampled pipeline.
- Generate training datasets with manifests, replay records, progress, and cancellation.
- Transform paired class-ID masks, boxes, and keypoints alongside geometric image operations.
- Export a portable dataset-generation ZIP containing code, recipe, and requirements.
- Build a portable Windows application and per-user installer using GitHub Actions.

The original `cv2_image_app.py` is preserved as a legacy PyQt5 prototype; the new
entry point is `workbench.py`, using PySide6. The legacy prototype is not part of the
new runtime and its PyQt5 dependency is not installed by the new requirements.

## Install and launch

Python 3.12 recommended. Run from this repository:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe make_demo.py
.\.venv\Scripts\python.exe workbench.py
```

On macOS/Linux use `.venv/bin/python`. In the author's existing workspace the sibling
`..\hybrid-rag\.venv\Scripts\python.exe` also works, but a separate environment is
recommended. The app requires no model download, paid API, or GPU.

## First workflow

1. Click **Add images** and select your images or the generated `data/demo/*.png` files.
2. Add Gaussian blur, grayscale, and Canny from the operation selector—or open
   `examples/edge_inspection.json`.
3. Adjust parameters. Changes preview automatically after a short debounce.
4. Select a step to edit it; check/uncheck to enable/disable it. Use Up/Down to reorder.
5. Use **Inspect stage** below the canvases to view intermediate results.
6. Enable **Exact full resolution** before judging the precise final output.
7. Save your JSON setup and choose **Export fixed Python**.

Mouse wheel zooms; drag pans; **Fit both views** resets the canvases. Keyboard shortcuts:
Ctrl+O adds images, Ctrl+S saves pipeline JSON, Ctrl+Z/Ctrl+Y undo/redo. Intermediate
stage selection affects inspection only; saved PNGs and scripts use the complete pipeline.

## Standalone exported code

The exported script embeds the same engine as the editor. It does not import Qt or
require this application to be installed. Install NumPy and OpenCV in its environment:

```sh
python -m pip install numpy opencv-python-headless
python process_images.py input.png output.png
python process_images.py input-folder output-folder
```

Single-image output must be PNG. Batch output preserves relative directories and appends
`.png` to each original filename (`part.jpg` becomes `part.jpg.png`) to avoid collisions
between input formats. Existing outputs are rejected unless `--overwrite` is passed.
Batch output cannot be inside the input folder. A failing image stops the batch; earlier
outputs may already exist. The source files are never modified.

Pipeline export contains operation IDs, ordered parameters, and enable states, not the
source image path. The exported script accepts new input/output paths at runtime.
Under the same dependency versions, lossless tests compare engine and export outputs
pixel for pixel. Install matching versions for cross-machine reproducibility.

## Operations and semantics

Resize (explicit width/height), bounded crop, fixed-canvas rotation, flip, grayscale,
brightness/contrast, gamma, Gaussian/median blur, fixed/Otsu/adaptive thresholding,
Canny, erosion/dilation/opening/closing, histogram equalization, and CLAHE.

- Internally images are RGB uint8 or genuine 2-D grayscale. Threshold and Canny explicitly
  convert RGB inputs to grayscale. Equalization/CLAHE act on Lab luminance for RGB inputs.
- Negative brightness clips at zero, rather than taking an absolute value.
- Gamma uses `output = 255 * (input / 255) ** (1 / gamma)`.
- Kernel/block sizes are positive odd values. Invalid pipelines are rejected rather
  than silently normalized on load/export.
- Crop bounds must fit the image at that stage. Different source sizes may require
  resizing first. Resize uses explicit dimensions and can change aspect ratio.
- Rotation preserves the canvas; corners may be clipped. Borders are selectable.
- PNG alpha is composited over white. 16-bit/float inputs are rejected; EXIF orientation
  is not applied automatically. This release is not a medical/raw-image workbench.

## Preview, performance, and history

Fast mode first reduces the input's longest edge to at most 1000 pixels. Settings then
operate on those preview pixels: pixel-sized kernels and crop coordinates can differ
from full-resolution behavior. Fast previews are labeled; export and saved PNG always
start with original pixels. Use exact mode for final comparison.

Preview work runs on a worker thread; stale requests are canceled/ignored. Prefix
caches are scoped to input content and configuration. Retained preview cache is capped
at 96 MiB; intermediate arrays are capped at 512 MiB. Reduce resolution or export the
pipeline if exact intermediate inspection exceeds the limit. A running OpenCV call
cannot be interrupted until it returns. Exact PNG saving is currently synchronous.
The last 100 configuration edits are retained for undo; image pixels are not history.
Stage timings include cache hits and are diagnostic, not benchmark measurements.

## Tests

```sh
python -m unittest discover -v
```

Tests cover all operations, ordering and disabled-step recomputation, cache isolation,
parameter validation, undo/redo, RGB/Unicode I/O, batch output guards, standalone export
equivalence, and offscreen Qt interactions. `tools/render_preview.py` renders a demo
window to `artifacts/workbench.png` for layout inspection.

GitHub Actions runs Windows tests and a Linux Docker build/test. The Docker image is
for headless engine/export/Qt tests; a Windows desktop app should be launched natively.

```sh
docker build -t cv2-workbench:test .
docker run --rm cv2-workbench:test
```

For headless exports, mount your files under `/work` and override the command, e.g.:

```sh
docker run --rm -v /absolute/path/to/files:/work cv2-workbench:test python /work/process_images.py /work/input.png /work/output.png
```

Linux bind mounts must be writable by container UID 10001. Docker does not provide a
desktop display here; no X11/VNC service or browser interface is bundled.

## Randomization and dataset generation

Select an operation, then **Random settings for selected step**. Set an application
probability and parameter rules. The current functional dialog uses validated JSON;
visual redesign and more polished range controls are a separate pass. Example rules
for brightness/contrast:

```json
{"brightness":{"min":-25,"max":25},"contrast":{"min":0.8,"max":1.2}}
```

For a blur kernel use `{"kernel":{"choices":[3,5,7]}}`. Numeric ranges are uniform;
integer upper bounds are inclusive, continuous samples use NumPy uniform, and kernel
ranges select only valid odd values. Categorical settings require choices. Probability
zero disables a step in every sample; a disabled pipeline step stays disabled. Random
rules must respect parameter bounds and joint constraints. For example, overlapping
Canny threshold ranges can produce invalid pairs and fail a generation run; they are
not silently swapped or repeatedly resampled.

The main editing canvas and **Export fixed Python** continue to use fixed parameter
values. Open **Dataset / random preview**, choose a seed and variant count, and sample
a contact sheet. It processes the first source at original resolution and displays up
to nine thumbnails. Samples remain fixed until you click sample again. Export the
first resolved sample as JSON or standalone Python, or export the entire random recipe
as a portable generation bundle.

The generation dialog uses gallery images as unlabeled training sources, or reads an
optional paired manifest. Choose a NEW output folder and click **Generate dataset**.
Generation runs off the UI thread; cancellation is checked between images. Closing an
active dialog first requests cancellation. OpenCV calls already running finish first.
Already generated outputs are kept on cancellation/failure, with status and error in
`run.json`; do not interpret partial output as a complete dataset.

### Manifest and paired annotations

Input is a JSON list, paths relative to that manifest:

```json
[
  {
    "id":"part-001", "image":"images/part.png", "split":"train",
    "mask":"masks/part.png",
    "boxes":[{"xyxy":[10,20,80,100],"label":"part"}],
    "keypoints":[{"x":25,"y":40,"visibility":2,"label":"corner"}]
  }
]
```

Only `image` and unique nonempty `id` are required; split defaults to train. Optional
splits are train, validation, and test. The manifest loader detects exact image-content
overlap across splits; CLI/UI select only training records for generation. Group related
source photographs by object/session before splitting: exact hashes cannot detect
near-duplicates. Changing file order does not change a source's sampled parameters.
For portable seeds across computers, assign stable manifest IDs; gallery-only mode
uses absolute image paths as IDs.

- Masks are single-channel uint8 or uint16 PNG class IDs matching image dimensions;
  geometry uses nearest-neighbor interpolation. Photometric changes never modify masks.
  Newly exposed rotation pixels use class ID 0, so reserve zero for background.
- Boxes use pixel, half-open `[x1,y1,x2,y2]` edges. Geometry transforms their corners,
  returns axis-aligned envelopes, clips bounds, and drops zero-area or insufficiently
  visible boxes. The visibility filter uses clipped envelope area, not polygon area.
  Rotated-box envelopes are approximate supervision and should be reviewed.
- Keypoints use pixel-center coordinates and visibility 0/1/2. Outside points are retained
  with visibility 0. Resize uses half-pixel center mapping; boxes use edge mapping.
- Rotation remains fixed-canvas. Reflect borders are rejected when annotations are
  present because reflected objects would lack corresponding labels. Use black/white.
- Only resize/crop/rotate/flip change annotation geometry. Edge/threshold/morphology
  preprocessing can change what is visible without changing the underlying labels;
  check that your pipeline remains appropriate for the target task.

This release uses the canonical manifest format above; direct COCO/YOLO file adapters,
polygons, instance-ID renumbering, and annotation painting are not included.

### Command-line generation and replay

To try all paired target types on generated example data:

```sh
python tools/make_paired_demo.py
python dataset.py generate data/paired-demo/inputs.json --recipe examples/random_preprocessing.json --output generated/paired-demo --variants 5 --seed 42
python dataset.py replay generated/paired-demo/replay.jsonl --row 0 --output artifacts/paired-replay.png
```

The example includes one source per split; only the training source is augmented.
Its uint16 mask deliberately uses class ID 300 to check class-ID preservation.

```sh
python dataset.py generate inputs.json --recipe examples/random_preprocessing.json --output generated/run-1 --variants 5 --seed 42
python dataset.py replay generated/run-1/replay.jsonl --row 0 --output replay.png
```

Outputs include PNG images/masks, `manifest.json`, `replay.jsonl`, and `run.json`.
Replay records contain the resolved pipeline, actual sampled values, input hashes,
source annotations, dropped boxes, output hash, and dependency versions. Replay uses
the saved resolved pipeline rather than sampling again, refuses changed sources, and
reports whether PNG encoding matches. Different dependency versions can change encoding
or pixels; keep the recorded versions for exact reproduction. Existing output folders
and replay companion files are never overwritten. Replay records contain local source
paths—keep them with private datasets rather than committing them to a public repository.

The **Replay generated record** button selects a zero-based record row and writes the
image, optional mask, and target JSON. Replay requires the original sources at their
recorded locations. Portable generation ZIPs contain code/configuration only, no images
or absolute input paths; after extraction run `python generate.py generate inputs.json
--output generated --variants 5 --seed 42` from that folder.

## Windows packaging and profiling

After a successful Actions run, download **CV2Workbench-Windows** from its artifacts.
It contains a portable `dist/CV2Workbench/` folder and
`installer-output/CV2Workbench-Setup.exe`. The installer installs for the current user
without requiring administrator rights. Builds are unsigned. The packaged application
includes runtime source resources so both export modes continue to work without Python
or this repository installed. Exported scripts/bundles still require a Python environment.

To build locally on Windows:

```powershell
python -m pip install pyinstaller
python -m PyInstaller --noconfirm workbench.spec
.\dist\CV2Workbench\CV2Workbench.exe --self-test
```

Compile `installer.iss` with Inno Setup to create the installer. CI builds it and checks
the packaged runtime before uploading the artifact. The installer adds shortcuts and
an uninstaller; datasets are saved to locations you choose, not bundled into the app.

```sh
python tools/profile_pipeline.py data/demo/example-1.png examples/edge_inspection.json --runs 10 --output artifacts/profile.json
```

Profiling reports warm CPU execution timings without prefix caching, input shape,
platform, and OpenCV version. It does not measure peak memory. UI redesign, painting,
compositing, drag-and-drop reordering, swipe comparison, webcam/video inputs, additional
library adapters, and broader real-dataset validation remain future work.

## Project layout

- `engine.py`: validation, operations, execution, image I/O, and export CLI runtime.
- `project.py`: configuration history and standalone-script generation.
- `workbench.py`: desktop editor, controls, canvases, and preview worker.
- `augmentation.py`, `dataset.py`: deterministic sampling, paired transforms, generation/replay.
- `generation_ui.py`: random settings, contact sheets, and cancellable generation dialog.
- `workbench.spec`, `installer.iss`: portable Windows application and installer build.
- `tests/`: engine/export and offscreen desktop tests.
- `examples/`: portable pipeline JSON.
- `cv2_image_app.py`: preserved original prototype.

License: Apache 2.0; see LICENSE.
