"""Publish only browser assets; cloud flag is generated, local defaults stay local."""
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
output = root / 'public'
output.mkdir(exist_ok=True)
for source in (root / 'frontend').iterdir():
    if source.is_file():
        shutil.copy2(source, output / source.name)
(output / 'runtime-config.js').write_text('window.ARENA_CLOUD = true;\n')
