# Optional GPU preprocessing

The Processing device selector controls preview and exact image saving. Auto uses CUDA when optional CUDA-enabled PyTorch and a GPU are available; otherwise it uses CPU. Explicit CUDA reports an error when unavailable. The preview shows the actual backend and per-step CPU/CUDA status in its tooltip.

CUDA operations: crop, flip, brightness/contrast, gamma, nearest-neighbor resize, and fixed threshold on grayscale inputs. Other operations use OpenCV on CPU and report mixed execution. Consecutive supported operations retain GPU data; intermediate previews and CPU operations require transfers. Small images or mixed pipelines may be slower on GPU.

Base requirements, the default container and packaged Windows builds remain CPU-compatible. Install requirements-gpu.txt in a separate CUDA-capable environment. A CPU-only PyTorch installation cannot use CUDA. Record installed versions and check torch.cuda.is_available() before profiling. No OpenCV CUDA build is required.

## CLI

```sh
python gpu_backend.py input.png examples/gpu_preprocessing.json --device cuda --strict --output outputs/gpu-result.png
```

Choose a new output path. A companion .execution.json records per-step devices/timings. Strict rejects CPU fallback. Standalone exported scripts and dataset generation/replay continue to use NumPy/OpenCV on CPU; GPU selection applies to preview and exact saving only.

## Optional Linux container

```sh
docker build --target gpu -t cv2-workbench:gpu .
docker run --rm --gpus all cv2-workbench:gpu python -c "import torch; print(torch.cuda.is_available())"
```

Mount inputs and an output directory when running the CLI. NVIDIA passthrough requires a compatible host driver and, on Windows, Docker/WSL2 GPU support. The optional target downloads CUDA dependencies and has not been independently rebuilt in this patch. GPU runtime checks used an existing CUDA-capable Linux validation image.

## Measured check — 13 November 2026

On my RTX 4060, a generated 2048×2048 RGB image with nearest resize, flip, brightness/contrast and gamma measured 37.46 ms CPU median and 9.49 ms CUDA median (20 iterations after 3 warmups, approximately 3.95× faster). Final uint8 output matched exactly in that run. Transfers were included; decoding, startup, intermediate previews and serialization were excluded.

This single synthetic recipe does not establish speed for arbitrary images, mixed operations, GUI responsiveness or detector accuracy. GPU regression tests also check nontrivial resize dimensions, crop and explicit mixed fallback. The workbench backend in edge-inference-benchmarks provides reproducible measurement.
