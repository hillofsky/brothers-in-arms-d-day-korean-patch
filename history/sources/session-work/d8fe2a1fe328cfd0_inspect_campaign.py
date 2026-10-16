from pathlib import Path
import struct
ram=Path('outputs/stage40p_campaign/controls_ram.bin').read_bytes()
for a in [0x08972360,0x08cc4390,0x08cc4480,0x08cc4580,0x0972385c,0x0972524c]:print(hex(a),ram[a-0x8000000:a-0x8000000+24].hex())
