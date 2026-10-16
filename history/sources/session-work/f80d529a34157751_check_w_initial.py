from pathlib import Path
import json,struct
r=Path('outputs/stage40w_validation/controls_ram.bin').read_bytes();a=0x9c1af84;print(struct.unpack_from('<H',r,a+0x50-0x8000000)[0])
