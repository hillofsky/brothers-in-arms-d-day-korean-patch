import json
from pathlib import Path
r=Path('outputs/stage43a_validation/controls_ram.bin').read_bytes();a=0x96eb630-0x8000000
print(r[a:a+100].hex())
