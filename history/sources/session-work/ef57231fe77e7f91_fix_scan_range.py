from pathlib import Path
p=Path(r'PROJECT_ROOT\bia_stage40i_tools\bia_stage40i_actual_resource_trace.py');s=p.read_text(encoding='utf-8');s=s.replace('RAM_START = 0x08800000','RAM_START = 0x08000000').replace('RAM_END = 0x0A800000','RAM_END = 0x0A000000');s=s.replace('''        except Exception:
            prev = b""
            addr += size
            continue
''','''        except Exception as exc:
            raise RuntimeError(f"RAM read failed at 0x{addr:08X}, size 0x{size:X}") from exc
        if len(block) != size:
            raise RuntimeError(f"Incomplete RAM read at 0x{addr:08X}: {len(block)}/{size}")
''');p.write_text(s,encoding='utf-8')
