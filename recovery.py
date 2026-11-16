"""Per-window recipe snapshots, separate from user-saved recipes and image data."""
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

import engine


class RecoveryStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        self.path = self.directory / f'recipe-{stamp}-{uuid.uuid4().hex}.json'

    def write(self, pipeline, source_path=None):
        pipeline = engine.validate(pipeline)
        self.directory.mkdir(parents=True, exist_ok=True)
        record = dict(schema_version=1, saved_at=datetime.now(timezone.utc).isoformat(),
                      source_path=str(source_path) if source_path is not None else None,
                      pipeline=pipeline)
        engine.atomic_write_json(self.path, record)
        return self.path

    def clear(self):
        # A window only removes the snapshot filename it generated itself.
        self.path.unlink(missing_ok=True)

    def available(self):
        return sorted(self.directory.glob('recipe-*.json'), reverse=True)


def read_snapshot(path):
    path = Path(path)
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Recovery snapshot exceeds the 4 MiB limit')
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(record, dict) or type(record.get('schema_version')) is not int or record['schema_version'] != 1:
            raise ValueError('Unsupported recovery snapshot')
        if record.get('source_path') is not None and not isinstance(record['source_path'], str):
            raise ValueError('Invalid recovery source path')
        record['pipeline'] = engine.validate(record['pipeline'])
        return record
    except (ValueError, KeyError, TypeError, RecursionError) as exc:
        raise ValueError('Invalid recovery snapshot; the current recipe has not been changed') from exc
