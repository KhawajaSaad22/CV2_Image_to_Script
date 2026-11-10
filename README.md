# CV2 Image to Script — Pipeline Workbench

A local desktop editor for building image-preprocessing pipelines, inspecting live
intermediate results, and exporting standalone OpenCV/NumPy code.

## Implemented: Phases 1–3

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
7. Save your JSON setup and choose **Export Python**.

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

## Later phases

Randomized parameter ranges, probabilities, sampled contact sheets, dataset generation,
per-sample replay manifests, and paired mask/box/keypoint transforms are **not** included
in Phases 1–3. Also deferred: pixel painting, Photoshop-style compositing layers,
drag-and-drop reordering, split/swipe comparison, video/webcam inputs, installer packaging,
and multi-library adapters. The operation engine is structured to support later additions.

## Project layout

- `engine.py`: validation, operations, execution, image I/O, and export CLI runtime.
- `project.py`: configuration history and standalone-script generation.
- `workbench.py`: desktop editor, controls, canvases, and preview worker.
- `tests/`: engine/export and offscreen desktop tests.
- `examples/`: portable pipeline JSON.
- `cv2_image_app.py`: preserved original prototype.

License: Apache 2.0; see LICENSE.
