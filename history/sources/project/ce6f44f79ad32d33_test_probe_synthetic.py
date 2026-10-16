# Offline self-test only. No WebSocket or real PSP files accessed.
import sys, hashlib, struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from live_font_probe import probe_memory,BASE

def verify():
    ram=bytearray(0x02000000)
    def set_u16(addr,x):struct.pack_into('<H',ram,addr-BASE,x)
    def set_u32(addr,x):struct.pack_into('<I',ram,addr-BASE,x)
    font=0x09B1CF24
    for offset,x in [(0x50,878)]:set_u16(font+offset,x)
    set_u32(font+0x54,0x09E6B020)
    set_u32(font+0x474,0x09E75B20)
    set_u32(font+0x478,0x09E75B30)
    set_u32(font+0x488,0x09E75B40)
    for i in range(4):
        set_u16(0x09E75B20+2*i,128)
        set_u16(0x09E75B30+2*i,256)
        set_u32(0x09E75B40+4*i,0x09A87FB0)
    ch='프';cp=ord(ch);page=0x09E10000
    set_u32(font+0x58+(cp>>8)*4,page)
    set_u16(page+(cp&255)*2,795)
    set_u16(0x09E6B020+795*24,cp)
    hello='프랑스 유타 해변 인근'.encode('utf8')
    ram[0x3000:0x3000+len(hello)]=hello
    font_sha=hashlib.sha256(ram[font-BASE:font-BASE+0x490]).hexdigest()
    atlas=0x09DF3020
    atlas_sha=hashlib.sha256(ram[atlas-BASE:atlas-BASE+0x20000]).hexdigest()
    expected={'font_objects':[{'runtime':hex(font),'sha256':font_sha}],
        'runtime_probe_cps':[ch], 'atlas_runtime_base':hex(atlas),
        'atlas_128k_sha256':atlas_sha,'strings':['프랑스 유타 해변 인근']}
    r=probe_memory(ram,expected)
    assert r['fonts'][0]['glyph_count']==878
    assert r['fonts'][0]['chars'][ch]['codepoint_verified']
    assert r['fonts'][0]['renderer_page_arrays']['widths']==[128]*4
    assert r['fonts'][0]['renderer_page_arrays']['heights']==[256]*4
    assert r['strings'][0]['addresses']==['0x08003000']
    assert r['atlas']['byte_identical']
    print('PASS: synthetic memory glyph/page pointers, 4-page metrics, strings, atlas checks')
if __name__=='__main__':verify()
