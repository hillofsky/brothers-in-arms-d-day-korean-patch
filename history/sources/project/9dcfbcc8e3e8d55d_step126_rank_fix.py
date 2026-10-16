#!/usr/bin/env python3
"""STEP126 surgical correction. Changes *only* exact '하지만 병장님' to '하지만 중사님'
when verified in one active ISO9660 resource. Otherwise creates a diagnostic failure report.
Requires Python standard library only; never opens emulator or save directories.
"""
import argparse, datetime, hashlib, json, os, shutil, sys, traceback
from pathlib import Path

SECTOR=2048
CHUNK=8*1024*1024
SOURCE=Path(r'PROJECT_ROOT\BIA_STEP125_SPEAKER_BREAKS_KO_TEST.iso')
TARGET=Path(r'PROJECT_ROOT\BIA_STEP126_LEGGETT_MAC_RANK_KO_TEST.iso')
SOURCE_SHA256='6d431b60b0ba23ff01347cfd9ee8393a2bc7d55047ba1d4daafbc1ef82a433fb'
SOURCE_LENGTH=3311890432
SPEAKER_PATCH_OFFSETS=(406139650,596545827,656706641)

class ISO:
    def __init__(self,p):
        self.h=open(p,'rb'); self.p=Path(p)
        pvd=self.read(16*SECTOR,SECTOR)
        if pvd[:7]!=b'\x01CD001\x01':raise ValueError('Invalid ISO9660 PVD')
        if int.from_bytes(pvd[128:130],'little')!=SECTOR:raise ValueError('Unexpected sector size')
        self.root=self.entry(pvd,156)
        if self.root is None or not self.root['directory']:raise ValueError('No root directory')
    def read(self,offset,n):
        self.h.seek(offset);d=self.h.read(n)
        if len(d)!=n:raise IOError(f'Short ISO read at {offset}')
        return d
    def entry(self,buf,off):
        n=buf[off]
        if not n:return None
        e=buf[off:off+n]
        if n<34 or len(e)!=n:raise ValueError('Bad directory entry')
        sz=e[32];name=e[33:33+sz]
        if sz+33>len(e):raise ValueError('Bad name')
        if name==b'\0':name='.'
        elif name==b'\1':name='..'
        else:name=name.decode('ascii','replace').split(';')[0]
        return dict(name=name,lbn=int.from_bytes(e[2:6],'little'),size=int.from_bytes(e[10:14],'little'),directory=bool(e[25]&2))
    def list_all(self):
        out=[];dirs=[('',self.root)];seen=set()
        while dirs:
            pre,dr=dirs.pop(0);token=(dr['lbn'],dr['size'])
            if token in seen:continue
            seen.add(token)
            if dr['size']>64*1024*1024:raise ValueError('Unexpected ISO directory size')
            b=self.read(dr['lbn']*SECTOR,dr['size']);i=0
            while i<len(b):
                if b[i]==0:i=(i//SECTOR+1)*SECTOR;continue
                n=b[i]
                e=self.entry(b,i)
                i += n
                if not e:break
                if e['name'] in ('.','..'):continue
                path=f'{pre}/{e["name"]}'
                if e['directory']:dirs.append((path,e))
                else:e['path']=path;out.append(e)
        return out
    def close(self):self.h.close()


def collect_matches(iso,entries,report):
    needles=[]
    for coding in ('utf-8','utf-16le'):
        for term in ('하지만 병장님','병장님','하지만 중사님','레겟:'):
            needles.append((coding,term,term.encode(coding)))
    matches=[];scanned=0
    targets=[e for e in entries if e['path'].upper().endswith(('.MDI','.INT','.ST1','.TXT','.BIN')) and e['size']>0]
    for e in targets:
        # bounded block scan; boundaries are overlapping so no token is missed
        prev=b'';off=0
        while off<e['size']:
            dat=iso.read(e['lbn']*SECTOR+off,min(CHUNK,e['size']-off))
            blob=prev+dat;start=off-len(prev)
            for coding,term,needle in needles:
                j=blob.find(needle)
                while j>=0:
                    within=start+j
                    if within>=0 and within+len(needle)<=e['size']:
                        if not (j<len(prev) and j+len(needle)<=len(prev)):
                            before=blob[max(0,j-120):j];after=blob[j+len(needle):j+len(needle)+120]
                            r=dict(file=e['path'],file_size=e['size'],encoding=coding,
                              matched=term,offset_in_file=within,absolute_offset=e['lbn']*SECTOR+within,
                              before_hex=before.hex(),after_hex=after.hex())
                            # human-readable context as an aid, may contain arbitrary data
                            for fmt in (coding,):
                                r['context_preview']=(blob[max(0,j-70):min(len(blob),j+len(needle)+70)]).decode(fmt,'replace')[:180]
                            matches.append(r)
                    j=blob.find(needle,j+1)
            prev=blob[-64:];off+=len(dat);scanned+=len(dat)
    report['active_file_count']=len(entries)
    report['searched_resource_count']=len(targets)
    report['resource_bytes_scanned']=scanned
    report['matches']=matches[:300]
    report['match_count']=len(matches)
    return matches


def validate_preflight(src,matches,iso,report):
    if src.stat().st_size!=SOURCE_LENGTH:
        raise ValueError('Unexpected STEP125 length; source identity not proven')
    for p in SPEAKER_PATCH_OFFSETS:
        if iso.read(p,1)!=b'\\':raise ValueError(f'STEP125 speaker boundary marker not found at {hex(p)}')
    anchors=[x for x in matches if x['matched']=='하지만 병장님']
    report['exact_phrase_matches']=anchors
    if not anchors:
        raise ValueError('Exact phrase not found in plain UTF-8/UTF-16LE active ISO resources. Source likely custom-encoded/compressed or phrase differs. No patch; use diagnostics.')
    if len(anchors)!=1:
        raise ValueError(f'Exact phrase ambiguous ({len(anchors)} matches), no automatic patch')
    a=anchors[0]
    if not a['file'].upper().endswith(('.MDI','.INT')):
        raise ValueError('Phrase found outside text-bearing MDI/INT; manual identification required')
    old='하지만 병장님'.encode(a['encoding']);new='하지만 중사님'.encode(a['encoding'])
    if len(old)!=len(new):raise ValueError('Replacement size mismatch')
    if iso.read(a['absolute_offset'],len(old))!=old:raise ValueError('Source bytes changed after scan')
    # restrict by exact context: no other occurrences changed
    report['patch']={k:a[k] for k in ('file','encoding','offset_in_file','absolute_offset')}
    report['patch'].update(from_hex=old.hex(),to_hex=new.hex(),old='하지만 병장님',new='하지만 중사님')
    return a['absolute_offset'],old,new


def create_iso(src,dst,at,old,new,report):
    if dst.exists():raise FileExistsError('Target already exists; never overwrite: '+str(dst))
    if shutil.disk_usage(dst.parent).free<src.stat().st_size+256*1024*1024:
        raise OSError('Insufficient disk space for non-destructive ISO copy (+256MiB margin)')
    temp=dst.with_name(dst.name+'.STEP126_'+str(os.getpid())+'.part')
    total=0;src_hash=hashlib.sha256();out_hash=hashlib.sha256();diffs=0
    try:
        with src.open('rb') as fi,temp.open('xb') as fo:
            while True:
                block=fi.read(CHUNK)
                if not block:break
                src_hash.update(block)
                b=bytearray(block)
                # Exact replacement can straddle copy-chunk boundaries.
                # Preflight already guaranteed bytes; patch overlapping segment only.
                left=max(total,at);right=min(total+len(b),at+len(old))
                if left<right:
                    start=left-total;end=right-total
                    orig=old[left-at:right-at]
                    if b[start:end]!=orig:raise ValueError('Input changed during copy')
                    b[start:end]=new[left-at:right-at]
                    diffs+=sum(x!=y for x,y in zip(orig,new[left-at:right-at]))
                fo.write(b);out_hash.update(b);total+=len(b)
                if total%(CHUNK*32)==0: print('COPY',round(total/src.stat().st_size*100,1),'%',flush=True)
            fo.flush();os.fsync(fo.fileno())
        report['source_sha256']=src_hash.hexdigest()
        if report['source_sha256']!=SOURCE_SHA256:raise ValueError('Source ISO SHA256 mismatch; candidate output discarded')
        if total!=src.stat().st_size:raise ValueError('Source size changed')
        if diffs!=sum(x!=y for x,y in zip(old,new)):
            raise ValueError('Unexpected edit count')
        with temp.open('rb') as f:
            f.seek(at)
            if f.read(len(new))!=new:raise ValueError('Independent output readback failed')
            f.seek(at)
            if f.read(len(new))==old:raise ValueError('Old text remained')
        report['target_sha256']=out_hash.hexdigest()
        report['changed_bytes']=diffs
        report['output_size']=total
        # Full-file readback independent of bytes streamed to hash
        h=hashlib.sha256()
        with temp.open('rb') as f:
            for b in iter(lambda:f.read(CHUNK),b''):h.update(b)
        if h.hexdigest()!=report['target_sha256']:
            raise ValueError('Final SHA256 readback failed')
        report['full_iso_sha256_verified']=True
        if dst.exists():raise FileExistsError('Refusing overwrite (race)')
        if os.name=='nt':os.rename(temp,dst)
        else:os.link(temp,dst);temp.unlink()
        print('OUTPUT',dst,flush=True)
    finally:
        if temp.exists():temp.unlink()


def append_state(root,report):
    p=root/'PROJECT_STATE.md'
    if not p.is_file():return 'missing'
    tag='<!-- STEP126_LEGGETT_RANK_BEGIN -->'
    s=p.read_text(encoding='utf-8-sig')
    if tag in s:return 'already_exists'
    rec=('\n\n'+tag+'\n## STEP126 — Leggett addressing Mac by rank\n'
         +'Status: BUILT_UNVERIFIED; real runtime verification pending.\n'
         +'Source: '+report['source']+'\nOutput: '+report['target']+'\n'
         +'Corrected one exact text field: 하지만 병장님 -> 하지만 중사님.\n'
         +'Active resource: '+report['patch']['file']+'\n'
         +'Source SHA256: '+report['source_sha256']+'\n'
         +'Target SHA256: '+report['target_sha256']+'\n'
         +'Other bytes unchanged; STEP125 user runtime check of font and speaker breaks still baseline.\n'
         +'Other Leggett Sergeant contexts and icon bugs unverified; user PPSSPP and saves untouched.\n'
         +'<!-- STEP126_LEGGETT_RANK_END -->\n')
    with p.open('a',encoding='utf-8',newline='') as f:f.write(rec)
    return 'appended'



def collect_local_builder_sources(report_dir):
    """On a blocked patch, collect bounded parser/builder source for the next precise fix."""
    work=Path(r'SESSION_SESSION_WORK')
    if not work.is_dir():return []
    selected=[];total=0
    words=('mdi','iso','fstring','patch','audit','build124','verify124','decode','stream','font')
    for p in sorted(work.glob('*.py'),key=lambda p:(not ('124' in p.name),p.name.lower())):
        if not any(w in p.name.lower() for w in words):continue
        n=p.stat().st_size
        if not (0<n<=800000 and total+n<=6000000):continue
        d=report_dir/'parser_source';d.mkdir(exist_ok=True)
        shutil.copy2(p,d/p.name)
        selected.append(p.name);total+=n
    return selected

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',default=str(SOURCE));ap.add_argument('--target',default=str(TARGET));ap.add_argument('--report-dir',required=True)
    ap.add_argument('--dry-run',action='store_true');ap.add_argument('--no-state-update',action='store_true')
    a=ap.parse_args()
    src=Path(a.source);dst=Path(a.target);dir=Path(a.report_dir);dir.mkdir(parents=True,exist_ok=True)
    report={'step':'STEP126','source':str(src),'target':str(dst),'status':'PREFLIGHT','runtime_verified':False,
       'user_emulator_untouched':True,'source_iso_untouched':True,'saves_untouched':True,
       'request':'Leggett addresses Mac, Staff Sergeant, as 중사님 rather than 병장님'}
    rp=dir/'diagnosis.json'
    try:
        if not src.is_file():raise FileNotFoundError('STEP125 source not found')
        if src.resolve()==dst.resolve():raise ValueError('Refusing same source/destination')
        if dst.exists():raise FileExistsError('Target exists; refuse overwrite')
        iso=ISO(src)
        try:
            entries=iso.list_all()
            match=collect_matches(iso,entries,report)
            at,old,new=validate_preflight(src,match,iso,report)
        finally:iso.close()
        report['status']='PREFLIGHT_PASS';rp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        if a.dry_run:
            report['status']='PREFLIGHT_PASS_NO_ISO';print('DRY_RUN_PASS',flush=True)
        else:
            create_iso(src,dst,at,old,new,report)
            report['status']='BUILT_UNVERIFIED'
            if not a.no_state_update:report['project_state_update']=append_state(src.parent,report)
        print('SUCCESS',report['status'],flush=True)
        return 0
    except Exception as ex:
        report['status']='BLOCKED_NO_CHANGES'
        report['error']=str(ex)
        report['traceback']=traceback.format_exc()
        try:report['collected_parser_sources']=collect_local_builder_sources(dir)
        except Exception as collection_error:report['collection_warning']=str(collection_error)
        print('BLOCKED_NO_CHANGES:',ex,flush=True)
        return 2
    finally:
        rp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':sys.exit(main())
