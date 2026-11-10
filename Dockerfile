FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 QT_QPA_PLATFORM=offscreen
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libegl1 libgl1 libopengl0 libglib2.0-0 libdbus-1-3 libxkbcommon0 libfreetype6 libfontconfig1 libxrender1 libsm6 libice6 fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt && python -m pip check
COPY . .
RUN useradd --create-home --uid 10001 app && mkdir -p /work && chown -R app:app /app /work
USER app
RUN python -m unittest discover -v
CMD ["python", "-m", "unittest", "discover", "-v"]
