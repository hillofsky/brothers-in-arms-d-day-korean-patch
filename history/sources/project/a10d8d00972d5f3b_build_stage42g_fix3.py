#!/usr/bin/env python3
import argparse, hashlib, json, shutil, struct, sys
from pathlib import Path

SECTOR=2048

OLD_WORDS=[
    0x34060080, # li a2,0x80   = texture height 128
    0x34070100, # li a3,0x100  = texture width/tbw 256
    0x8FA80000, # lw t0,0(sp)
    0x8D080014, # lw t0,0x14(t0)
    0x00002025, # li a0,0
    0x00E02825, # move a1,a3
]
OLD_SIG=b''.join(struct.pack('<I',x) for x in OLD_WORDS)
NEW_H=0x34060200 # li a2,0x200 = 512
NEW_W=0x34070200 # li a3,0x200 = 512

def sha1(b): return hashlib.sha1(b).hexdigest()

class ISO:
    def __init__(self,p):
        self.p=Path(p)
        self.f=self.p.open('r+b')
        pvd=self.read(16*SECTOR,SECTOR)
        if pvd[0]!=1 or pvd[1:6]!=b'CD001':
            raise ValueError('Not ISO9660')
        self.root=self.parse(pvd,156,16*SECTOR+156)
    def read(self,o,n):
        self.f.seek(o); b=self.f.read(n)
        if len(b)!=n: raise EOFError((o,n,len(b)))
        return b
    def write(self,o,b):
        self.f.seek(o); self.f.write(b)
    def parse(self,buf,o,record_abs):
        ln=buf[o]
        if not ln: return None
        r=buf[o:o+ln]
        nl=r[32]; rn=r[33:33+nl]
        name='.' if rn==b'\0' else ('..' if rn==b'\1' else rn.decode('ascii','replace').split(';',1)[0])
        return {
            'name':name,
            'extent':int.from_bytes(r[2:6],'little'),
            'size':int.from_bytes(r[10:14],'little'),
            'dir':bool(r[25]&2),
            'record_abs':record_abs,
        }
    def children(self,n):
        base=n['extent']*SECTOR
        data=self.read(base,n['size'])
        out=[]; o=0
        while o<len(data):
            ln=data[o]
            if ln==0:
                o=((o//SECTOR)+1)*SECTOR
                continue
            r=self.parse(data,o,base+o)
            if r and r['name'] not in ('.','..'): out.append(r)
            o+=ln
        return out
    def walk(self):
        st=[('',self.root)]
        while st:
            base,n=st.pop()
            for c in self.children(n):
                p=(base+'/'+c['name']).replace('//','/')
                yield p,c
                if c['dir']: st.append((p,c))
    def close(self): self.f.close()

def all_occurrences(data,needle):
    out=[]; pos=0
    while True:
        i=data.find(needle,pos)
        if i<0: return out
        out.append(i); pos=i+1

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',required=True)
    ap.add_argument('--output',required=True)
    ap.add_argument('--report',required=True)
    a=ap.parse_args()

    src=Path(a.source); dst=Path(a.output)
    if not src.exists(): raise FileNotFoundError(src)
    if dst.exists(): raise FileExistsError(f'Refusing overwrite: {dst}')
    shutil.copyfile(src,dst)

    iso=ISO(dst)
    rep={
        'stage':'42G_FIX3_512_TEXTURE_DIMENSION_PATCH',
        'source':str(src),'output':str(dst),
        'runtime_evidence':{
            'height_address':'0x0893D968',
            'height_before':'0x34060080',
            'height_after':'0x34060200',
            'width_tbw_address':'0x0893D96C',
            'width_tbw_before':'0x34070100',
            'width_tbw_after':'0x34070200',
            'nearby_call':'0x0893D980 -> 0x0881DB24',
            'note':'Only the proven 128/256 texture-image dimensions are patched. 0x400 at 0x0893D878 is intentionally untouched.'
        },
        'scan_candidates':[],
        'hits':[],
    }

    try:
        candidates=[]
        for path,node in iso.walk():
            if node['dir']: continue
            name=node['name'].upper()
            if name.endswith('.PRX') or name in ('BOOT.BIN','EBOOT.BIN'):
                candidates.append((path,node))

        for path,node in candidates:
            data=iso.read(node['extent']*SECTOR,node['size'])
            offs=all_occurrences(data,OLD_SIG)
            rec={
                'path':path,'name':node['name'],'lbn':node['extent'],'size':node['size'],
                'sha1':sha1(data),'signature_hits':[f'0x{x:X}' for x in offs],
            }
            rep['scan_candidates'].append(rec)
            for off in offs:
                rep['hits'].append({
                    'path':path,'lbn':node['extent'],'file_offset':off,
                    'file_offset_hex':f'0x{off:X}',
                    'before_hex':data[off:off+48].hex(),
                })

        if len(rep['hits'])!=1:
            raise RuntimeError(f'Expected exactly 1 texture-dimension signature hit, found {len(rep["hits"])}')

        hit=rep['hits'][0]
        target=next((x for x in candidates if x[0]==hit['path']),None)
        if target is None: raise RuntimeError('Internal target lookup failed')
        path,node=target
        data=bytearray(iso.read(node['extent']*SECTOR,node['size']))
        off=hit['file_offset']

        before_h=struct.unpack_from('<I',data,off)[0]
        before_w=struct.unpack_from('<I',data,off+4)[0]
        if before_h!=OLD_WORDS[0] or before_w!=OLD_WORDS[1]:
            raise RuntimeError('Signature changed before patch')

        struct.pack_into('<I',data,off,NEW_H)
        struct.pack_into('<I',data,off+4,NEW_W)
        iso.write(node['extent']*SECTOR,data)

        verify=iso.read(node['extent']*SECTOR,node['size'])
        after_h=struct.unpack_from('<I',verify,off)[0]
        after_w=struct.unpack_from('<I',verify,off+4)[0]
        if after_h!=NEW_H or after_w!=NEW_W:
            raise RuntimeError('Patch readback failed')

        hit.update({
            'patched_file':path,
            'file_sha1_after':sha1(verify),
            'height_word_after':f'0x{after_h:08X}',
            'width_word_after':f'0x{after_w:08X}',
            'after_hex':verify[off:off+48].hex(),
        })
        rep['completed']=True
        rep['output_size']=dst.stat().st_size
    finally:
        iso.close()

    Path(a.report).write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(rep,ensure_ascii=False,indent=2))

if __name__=='__main__':
    sys.exit(main())
