#!/usr/bin/env python3
# BIA STEP125 — surgical, speaker-aware subtitle newline restoration.
# Pure standard-library; never writes source ISO or PPSSPP files.
import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import struct
import sys
import time
import traceback
from pathlib import Path

SECTOR=2048
CHUNK=8*1024*1024
DEFAULT_SOURCE=Path(r'PROJECT_ROOT\BIA_STEP124_TEXT_REVIEW_KO_TEST.iso')
DEFAULT_TARGET=Path(r'PROJECT_ROOT\BIA_STEP125_SPEAKER_BREAKS_KO_TEST.iso')

class Iso9660:
    def __init__(self,p):
        self.path=Path(p)
        self.h=self.path.open('rb')
        b=self.read(16*SECTOR,SECTOR)
        if b[0]!=1 or b[1:6]!=b'CD001' or b[6]!=1:
            raise ValueError('Not ISO9660 Primary Volume Descriptor at sector 16')
        if int.from_bytes(b[128:130],'little')!=SECTOR:
            raise ValueError('Unexpected ISO logical sector size')
        self.volume=b[40:72].decode('ascii','replace').strip()
        self.root=self.parse(b,156)
        if not self.root or not self.root['dir']:
            raise ValueError('Invalid ISO9660 root directory')
    def read(self,at,n):
        self.h.seek(at)
        b=self.h.read(n)
        if len(b)!=n:raise EOFError('ISO short read at '+hex(at))
        return b
    @staticmethod
    def parse(b,p):
        if p>=len(b) or not b[p]:return None
        n=b[p]
        if n<34 or p+n>len(b):raise ValueError('Invalid ISO9660 directory record')
        r=b[p:p+n]
        namelen=r[32]
        if 33+namelen>len(r):raise ValueError('Broken ISO9660 filename')
        raw=r[33:33+namelen]
        name='.' if raw==b'\0' else '..' if raw==b'\1' else raw.decode('ascii','replace').split(';')[0]
        return {'name':name,'lbn':int.from_bytes(r[2:6],'little'),
                'size':int.from_bytes(r[10:14],'little'),'dir':bool(r[25]&2)}
    def children(self,d):
        blob=self.read(d['lbn']*SECTOR,d['size']);p=0
        while p<len(blob):
            n=blob[p]
            if not n:
                p=(p//SECTOR+1)*SECTOR
                continue
            f=self.parse(blob,p)
            if f and f['name'] not in ('.','..'):yield f
            p+=n
    def locate(self,components):
        node=self.root
        for component in components:
            if not node['dir']:raise ValueError('Path traverses non-directory '+component)
            found=[e for e in self.children(node) if e['name'].upper()==component.upper()]
            if len(found)!=1:raise FileNotFoundError('Ambiguous or missing ISO entry: '+repr(component)+', found '+str(len(found)))
            node=found[0]
        if node['dir']:raise ValueError('Expected file, not directory')
        return node
    def close(self):self.h.close()


def find_offsets(data,pattern):
    at=0;out=[]
    while True:
        at=data.find(pattern,at)
        if at<0:break
        out.append(at);at+=1
    return out


def prepare_patches(source,definitions):
    iso=Iso9660(source)
    try:
        if len(definitions['patch_fields'])!=3:raise ValueError('Expected 3 speaker transitions')
        patches={};rows=[]
        for f in definitions['patch_fields']:
            name=f['file'];idx=f['field_index']
            if not name.upper().endswith('.ST1'):raise ValueError('Non-ST1 patch blocked')
            n=iso.locate(['PSP_GAME','USRDIR','SYSTEM',name])
            buf=iso.read(n['lbn']*SECTOR,n['size'])
            old=bytes.fromhex(f['encoded_step124']);new=bytes.fromhex(f['encoded_step125'])
            di=[i for i,(a,b) in enumerate(zip(old,new)) if a!=b]
            if len(old)!=len(new) or len(di)!=1 or old[di[0]]!=0x20 or new[di[0]]!=0x5c or f['byte_index']!=di[0]:
                raise ValueError('Unsafe changed-byte contract for '+name)
            lo=max(0,f['field_offset']-16)
            hi=min(len(buf),f['field_offset']+f['field_bytes']+128)
            local=find_offsets(buf[lo:hi],old)
            expected=[x+lo for x in local]
            already=find_offsets(buf[lo:hi],new)
            if len(expected)!=1:
                raise ValueError(f'{name} field {idx} preflight expected exactly one STEP124 field near 0x{f["field_offset"]:X}; found {expected}. STEP125-matches: {[x+lo for x in already]}. Source/version mismatch; nothing modified.')
            pos=expected[0]
            # The complete token byte sequence must be located near its indexed ST1 field.
            if pos<f['field_offset']-16 or pos>f['field_offset']+f['field_bytes']+128:
                raise ValueError('Subtitle field anchor outside original field extent')
            abs_at=n['lbn']*SECTOR+pos+di[0]
            if abs_at in patches:raise ValueError('Duplicate patch offsets')
            patches[abs_at]=(0x20,0x5c)
            rows.append({'file':name,'field_index':idx,'iso_file_lbn':n['lbn'],
              'iso_file_size':n['size'],'field_offset_original':f['field_offset'],
              'found_encoded_start':pos,'bytes_from_anchor':pos-f['field_offset'],
              'source_encoded_hex':old.hex(),'corrected_encoded_hex':new.hex(),
              'absolute_iso_patch_offset':abs_at,'absolute_iso_patch_offset_hex':hex(abs_at),
              'from_hex':'20','to_hex':'5c','intended_korean':f['korean']})
        return iso.volume,patches,rows
    finally:
        iso.close()


def sha256_file(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(CHUNK),b''):h.update(block)
    return h.hexdigest()


def build(source,target,patches,report):
    if target.exists():raise FileExistsError('Refusing overwrite of existing target ISO: '+str(target))
    if not source.is_file():raise FileNotFoundError('Source ISO missing: '+str(source))
    src_before=source.stat()
    disk_free=shutil.disk_usage(target.parent).free
    if disk_free<src_before.st_size+256*1024*1024:
        raise OSError('Insufficient free space: need full ISO copy + 256 MiB margin, free='+str(disk_free))
    temp=target.with_name(target.name+'.building_'+str(os.getpid())+'.part')
    if temp.exists():raise FileExistsError('Refusing overwrite of existing temporary file '+str(temp))
    insum=hashlib.sha256();outsum=hashlib.sha256()
    locations=sorted(patches)
    total=0;mark=-1
    try:
        with source.open('rb') as inp, temp.open('xb') as out:
            while True:
                b=inp.read(CHUNK)
                if not b:break
                insum.update(b)
                blk=bytearray(b)
                for off in locations:
                    if total<=off<total+len(blk):
                        from_byte,to_byte=patches[off]
                        if blk[off-total]!=from_byte:raise ValueError('ISO changed during copying at '+hex(off))
                        blk[off-total]=to_byte
                out.write(blk)
                outsum.update(blk)
                total+=len(blk)
                pct=(total*100)//src_before.st_size
                if pct//10!=mark:
                    mark=pct//10
                    print(f'COPY_AND_PATCH {pct:3}% ({total}/{src_before.st_size} bytes)',flush=True)
            out.flush();os.fsync(out.fileno())
        if total!=src_before.st_size:raise IOError('Size mismatch during ISO copy')
        src_after=source.stat()
        if (src_after.st_size,src_after.st_mtime_ns)!=(src_before.st_size,src_before.st_mtime_ns):
            raise RuntimeError('Source ISO modified concurrently; temporary output discarded')
        actual=sha256_file(temp)
        if actual!=outsum.hexdigest():raise IOError('Copied ISO SHA256 mismatch; temporary output discarded')
        with temp.open('rb') as f:
            for at,(before,after) in patches.items():
                f.seek(at)
                if f.read(1)!=bytes([after]):raise IOError('Readback patch mismatch '+hex(at))
        report['source_sha256']=insum.hexdigest()
        report['expected_target_sha256']=outsum.hexdigest()
        report['target_sha256']=actual
        report['size_bytes']=total
        report['byte_differences_from_source']=len(patches)
        report['entire_output_sha256_verified']=True
        report['other_bytes_unchanged']=True
        # Atomic non-destructive promotion on Windows: do not overwrite existing target.
        if target.exists():raise FileExistsError('Target was created during build; no overwrite')
        if os.name=='nt':
            os.rename(temp,target)  # Win32 MoveFile refuses existing destination.
        else:
            os.link(temp,target) # exclusive creation, avoids POSIX rename overwrite
            temp.unlink()
        return report
    finally:
        if temp.exists():
            try:temp.unlink()
            except OSError:print('WARNING: temporary file could not be removed: '+str(temp),flush=True)


def update_state(root,report,logdir):
    state=root/'PROJECT_STATE.md'
    if not state.exists():return 'state_file_missing'
    with state.open('r',encoding='utf-8-sig') as f:s=f.read()
    tag='<!-- STEP125_SPEAKER_BREAKS_SAFE_BEGIN -->'
    if tag in s:return 'already_updated'
    block=(f'\n\n{tag}\n## STEP125 — Restore movie subtitles at speaker transitions\n'
       f'Date: {dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
       f'Status: BUILT_UNVERIFIED (STATIC_READBACK_PASS, RUNTIME_QA_PENDING).\n'
       f'Source: {report["source"]}\n'
       f'Output: {report["target"]}\n'
       f'Source SHA256: {report["source_sha256"]}\n'
       f'Target SHA256: {report["target_sha256"]}\n'
       f'Preserved STEP124 as original source; three one-byte 0x20->0x5C speaker boundaries corrected: '
       f'EM_1230_BOOKENDS2.ST1 field9, EM_VICTORYINCARETAN.ST1 field4, FM_0115EAGLESJUMP.ST1 field15.\n'
       f'No font/texture/PRX/text/ISO bytes changed elsewhere (entire-file SHA256 readback). '
       f'133 subtitle fields retain the STEP124 11px font; 130 others byte-for-byte inherited.\n'
       f'PPSSPP and saves untouched; runtime movie playback & menu overlap & ongoing noise/icon issues UNVERIFIED.\n'
       f'Step log: {str(logdir)}\n'
       f'<!-- STEP125_SPEAKER_BREAKS_SAFE_END -->\n')
    # Create small in-step backup before writing working state.
    backup=logdir/'PROJECT_STATE_before_STEP125.md';backup.write_text(s,encoding='utf-8')
    with state.open('a',encoding='utf-8',newline='') as f:f.write(block)
    return 'appended'


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',default=str(DEFAULT_SOURCE))
    ap.add_argument('--target',default=str(DEFAULT_TARGET))
    ap.add_argument('--report-dir',required=True)
    ap.add_argument('--no-state-update',action='store_true')
    ap.add_argument('--dry-run',action='store_true')
    args=ap.parse_args()
    source=Path(args.source);target=Path(args.target);logdir=Path(args.report_dir);logdir.mkdir(parents=True,exist_ok=True)
    report={'step':'STEP125','source':str(source),'target':str(target),'status':'PREFLIGHT',
            'runtime_verified':False,'ppsspp_touched':False,'saves_touched':False,
            'original_iso_touched':False,'source_step124_preserved':True,
            'subtitle_font_px_inherited':11,'source_title':'BIA STEP124','movie_fields_total':133}
    rp=logdir/'build_report.json'
    try:
        definitions=json.loads((Path(__file__).parent/'speaker_fields.json').read_text(encoding='utf-8-sig'))
        if source.resolve()==target.resolve():raise ValueError('Source=target! In-place ISO modification forbidden')
        if not source.is_file():raise FileNotFoundError('STEP124 source not found: '+str(source))
        volume,patches,rows=prepare_patches(source,definitions)
        report.update({'status':'PREFLIGHT_PASS','iso_volume':volume,'patches':rows,
                       'field_count':len(rows),'source_length_bytes':source.stat().st_size})
        rp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('PREFLIGHT_PASS — 3 exact one-byte subtitle corrections; all source fields matched.',flush=True)
        for row in rows:print('TARGET',row['file'],'field',row['field_index'],row['absolute_iso_patch_offset_hex'],flush=True)
        if args.dry_run:
            report['status']='PREFLIGHT_PASS_NO_ISO_CREATED'
        else:
            build(source,target,patches,report)
            # Independent ISO9660 parse and end-to-end corrected-token readback.
            iso=Iso9660(target)
            try:
                for row in rows:
                    node=iso.locate(['PSP_GAME','USRDIR','SYSTEM',row['file']])
                    dat=iso.read(node['lbn']*SECTOR,node['size'])
                    p=row['found_encoded_start'];expected=bytes.fromhex(row['corrected_encoded_hex'])
                    if dat[p:p+len(expected)]!=expected:raise ValueError('Subtitle final readback failed: '+row['file'])
                    if dat[p:p+len(expected)]==bytes.fromhex(row['source_encoded_hex']):raise ValueError('Old subtitle still present: '+row['file'])
            finally:iso.close()
            report['status']='BUILT_UNVERIFIED'
            report['static_readback_pass']=True
            report['other_subtitles_inherited_unchanged']=130
            if not args.no_state_update:
                try:report['project_state_update']=update_state(source.parent,report,logdir)
                except Exception as ex:
                    report['project_state_update']='failed: '+repr(ex)
                    (logdir/'STATE_UPDATE_WARNING.txt').write_text(traceback.format_exc(),encoding='utf-8')
            print('STEP125 STATIC PASS; runtime playback has NOT been tested.',flush=True)
        rp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        return 0
    except Exception as e:
        report['status']='FAILED'
        report['exception']=repr(e)
        rp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        (logdir/'FAILURE.txt').write_text(traceback.format_exc(),encoding='utf-8')
        print('FAILED:',e,flush=True)
        return 1

if __name__=='__main__':sys.exit(main())
