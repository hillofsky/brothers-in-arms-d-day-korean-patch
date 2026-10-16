#!/usr/bin/env python3
"""BIA STEP087: conservative, manifest-and-archive-verified housekeeping.
Only exact old incoming package copies or byte-identical archive-backed duplicates.
Never deletes ISOs, saves, source data, project state, archives or unverified evidence.
"""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import traceback
import zipfile

PROTECTED_EXT={'.iso','.cso','.chd','.pbp','.sav','.sfo','.ppst','.md','.zip','.7z','.rar','.ccs','.mdi','.dsx','.dsl','.dat','.idx','.pmf'}
COMPRESSED_DUMPS={ 'hotkey_ram_32MiB.zlib', 'live_psp_ram_32MiB.zlib' }


def digest_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def digest_zip(z,member):
    h=hashlib.sha256()
    with z.open(member,'r') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def is_reparse(p):
    try:
        st=p.lstat()
        return p.is_symlink() or bool(getattr(st,'st_file_attributes',0) & 0x400)
    except OSError:return True


def check_dir_tree_no_links(root):
    if is_reparse(root):return False
    for here,dirs,files in os.walk(root,followlinks=False):
        for name in dirs+files:
            if is_reparse(Path(here)/name):return False
    return True


def contents(root):
    for here,dirs,files in os.walk(root,followlinks=False):
        for name in files:
            yield Path(here)/name


def archive_matches(z, path, arcname):
    zi=next((i for i in z.infolist() if i.filename.replace('\\','/').strip('/')==arcname),None)
    return zi is not None and zi.file_size==path.stat().st_size and digest_file(path)==digest_zip(z,zi)


def disk(path):
    try:
        d=shutil.disk_usage(str(path))
        return {'total_bytes':d.total,'used_bytes':d.used,'free_bytes':d.free}
    except Exception as ex:return {'error':str(ex)}


def ensure_under(child,parent):
    return child.resolve().is_relative_to(parent.resolve())


def read_watch(root, rep):
    logs=root/'log'
    archives=sorted(logs.glob('bia_STEP_086_live_read_watch_*.zip'),key=lambda f:f.stat().st_mtime,reverse=True)
    archives=archives[:12]
    for a in archives:
        try:
            with zipfile.ZipFile(a) as z:
                keys={i.filename.replace('\\','/'):i for i in z.infolist()}
                k='outputs/step086_watch_report.json'
                if k not in keys:continue
                d=json.loads(z.read(keys[k]).decode('utf-8-sig'))
                if d.get('step')!='STEP_086':continue
                rep['input_archive']=str(a)
                rep['watch_status']=d.get('status')
                rep['target_hits']={x['name']:x.get('hits') for x in d.get('last_hits',[])}
                counter=collections.Counter()
                ra=collections.Counter()
                maddr=collections.Counter()
                for line in d.get('sampled_pc_logs',[]):
                    msg=line.get('message','')
                    m=re.search(r'pc=([0-9a-fA-F]+) ra=([0-9a-fA-F]+)',msg)
                    if m:
                        counter['0x'+m.group(1).upper()]+=1
                        ra['0x'+m.group(2).upper()]+=1
                    m2=re.search(r' at ([0-9a-fA-F]+):',msg)
                    if m2:maddr['0x'+m2.group(1).upper()]+=1
                rep['sampled_log_messages']=len(d.get('sampled_pc_logs',[]))
                rep['dropped_messages']=d.get('dropped_log_messages_locally',0)
                rep['top_pc_sample_only']=counter.most_common(20)
                rep['top_ra_sample_only']=ra.most_common(20)
                rep['sampled_memory_addresses']=maddr.most_common(20)
                rep['screenshot_name']=next((Path(k).name for k in keys if k.endswith('ppsspp_native_screen_at_key1.jpg')),None)
                rep['limitations']=['PC frequency is a sample capped by collector at 250 messages, not all 18093 reads.',
                                    'Zero page/pointer hits only applies to chosen watch windows and addresses.',
                                    'No automatic ISO or PSP RAM patch applied.']
                return
        except Exception as ex:rep.setdefault('input_warnings',[]).append({'archive':str(a),'error':str(ex)})
    rep['watch_status']='NO_LOCAL_STEP086_ARCHIVE_FOUND'


def cleanup_incoming(root,manifest,report):
    base=root/'incoming'
    if not base.is_dir():return
    for candidate in sorted(base.iterdir()):
        if not candidate.is_dir() or is_reparse(candidate):continue
        if not ensure_under(candidate,base):continue
        # These are prior, original auto-extracted package directories only.
        # Never remove the currently running STEP087 folder.
        choice=next((k for k in sorted(manifest,key=len,reverse=True) if candidate.name.startswith(k)),None)
        if choice is None:continue
        record={'target':str(candidate),'kind':'manifest-matched old extracted package', 'action':'retained'}
        report['cleanup'].append(record)
        if not check_dir_tree_no_links(candidate):
            record['reason']='reparse/link inside';continue
        files={f.relative_to(candidate).as_posix():f for f in contents(candidate)}
        m=manifest[choice]
        needed=set(m)
        cache={rel for rel in files if (rel.startswith('scripts/__pycache__/') or rel.startswith('__pycache__/')) and rel.endswith('.pyc')}
        unexpected=set(files)-needed-cache
        missing=needed-set(files)
        if missing or unexpected:
            record['reason']='extra or missing files; never delete user additions'
            record['missing']=sorted(missing)[:10];record['unexpected']=sorted(unexpected)[:10]
            continue
        wrong=[rel for rel,h in m.items() if digest_file(files[rel])!=h]
        if wrong:
            record['reason']='modified file(s)';record['modified']=wrong[:10];continue
        num_bytes=sum(f.stat().st_size for f in files.values())
        shutil.rmtree(candidate)
        record.update(action='deleted_verified_duplicate',saved_bytes=num_bytes,file_count=len(files))


def cleanup_log_duplicates(root,report):
    log=root/'log'
    if not log.is_dir():return
    for stepdir in sorted(log.iterdir()):
        if not stepdir.is_dir() or is_reparse(stepdir) or not re.fullmatch(r'STEP_0(?:8[3-6])(?:_FIX\d+)?',stepdir.name):continue
        if not ensure_under(stepdir,log):continue
        for run in sorted(stepdir.iterdir()):
            if not run.is_dir() or is_reparse(run) or not re.fullmatch(r'\d{8}_\d{6}_\d{3}_\d+',run.name):continue
            if not check_dir_tree_no_links(run):continue
            ars=sorted([x for x in log.glob('*'+run.name+'.zip') if x.is_file() and stepdir.name in x.name and (x.name.startswith('bia_') or x.name.startswith('fall_'))])
            if len(ars)!=1:continue
            arc=ars[0]
            try:
                with zipfile.ZipFile(arc) as z:
                    # Validate CRC + decompression on all result ZIP contents, not just header.
                    if z.testzip() is not None:raise ValueError('result archive CRC failure')
                    for dirname in ('zip_contents',):
                        p=run/dirname
                        if not p.is_dir() or is_reparse(p):continue
                        if not check_dir_tree_no_links(p):continue
                        fs=list(contents(p))
                        if not fs:continue
                        # Every file in zip_contents must match its result archive counterpart.
                        if all(archive_matches(z,f,f.relative_to(p).as_posix()) for f in fs):
                            n=sum(f.stat().st_size for f in fs)
                            shutil.rmtree(p)
                            report['cleanup'].append({'target':str(p),'kind':'duplicate ZIP staging tree','archive':str(arc),'action':'deleted_verified_duplicate','saved_bytes':n})
                        else:
                            report['cleanup'].append({'target':str(p),'kind':'ZIP staging tree','action':'retained','reason':'ZIP contents not identical'})
                    # RAM dump can be removed from outputs only when byte-for-byte archived.
                    for name in sorted(COMPRESSED_DUMPS):
                        p=run/'outputs'/name
                        if not p.is_file() or is_reparse(p):continue
                        if archive_matches(z,p,'outputs/'+name):
                            n=p.stat().st_size;p.unlink()
                            report['cleanup'].append({'target':str(p),'kind':'duplicate archived RAM dump','archive':str(arc),'action':'deleted_verified_duplicate','saved_bytes':n})
                        else:
                            report['cleanup'].append({'target':str(p),'action':'retained','reason':'archived copy missing or hash differs'})
            except Exception as ex:
                report['cleanup'].append({'target':str(run),'action':'retained','reason':'archive verification failed: '+str(ex)})


def largest_files(root,report):
    # Scan only inventory: NO automatic large-file deletion.
    ranking=[];n=0
    for here,dirs,files in os.walk(root,followlinks=False):
        dirs[:]=[x for x in dirs if not is_reparse(Path(here)/x)]
        for name in files:
            f=Path(here)/name
            try:
                if not is_reparse(f):
                    st=f.stat()
                    n+=1
                    if st.st_size>=20_000_000:ranking.append((st.st_size,str(f)))
            except OSError:pass
    report['inventory_scanned_files']=n
    report['largest_files_no_auto_delete']=[{'bytes':size,'path':path} for size,path in sorted(ranking,reverse=True)[:35]]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',required=True)
    p.add_argument('--manifest',required=True)
    p.add_argument('--out',required=True)
    a=p.parse_args()
    root=Path(a.root)
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    report={'step':'STEP_087','status':'RUNNING','root':str(root),'cleanup':[],
            'automatic_iso_delete':False,'automatic_savedata_delete':False,
            'automatic_archive_delete':False,'game_iso_writes':False}
    try:
        if not (root/'log').is_dir():raise RuntimeError('Expected PROJECT_ROOT\\log missing')
        manifest=json.loads(Path(a.manifest).read_text(encoding='utf-8-sig'))
        report['disk_before']=disk(root)
        read_watch(root,report)
        cleanup_incoming(root,manifest,report)
        cleanup_log_duplicates(root,report)
        largest_files(root,report)
        report['disk_after']=disk(root)
        report['bytes_deleted_verified']=sum(x.get('saved_bytes',0) for x in report['cleanup'] if x['action']=='deleted_verified_duplicate')
        report['deleted_count']=sum(x['action']=='deleted_verified_duplicate' for x in report['cleanup'])
        report['status']='COMPLETE_OFFLINE_DIAGNOSTIC_CLEANUP'
    except Exception as ex:
        report['status']='FAILED';report['error']=str(ex);report['traceback']=traceback.format_exc()
        raise
    finally:
        (out/'step087_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        n=report.get('bytes_deleted_verified',0)
        summary=f'''# BIA STEP 087 — Offline Trace Analysis & Verified Duplicate Cleanup\n\nStatus: {report['status']}\n\nVerified duplicate bytes reclaimed (not drive-wide prediction): {n:,}\nDeleted duplicate items: {report.get('deleted_count',0)}\nMission 2 UTF-8 string read hits: {report.get('target_hits',{}).get('mission2_utf8_source','unknown')}\nFont page and glyph pointer read hits: {[ (k,v) for k,v in report.get('target_hits',{}).items() if k!='mission2_utf8_source' ]}\nTop sampled PCs: {report.get('top_pc_sample_only',[])[:8]}\n\nNo ISO, save, project state, or evidence ZIP automatically removed. Large-file candidates are for manual review only; the mission 2 Korean `>` issue remains unresolved.\n'''
        (out/'STEP_087.md').write_text(summary,encoding='utf-8')
    print('STEP087:',report['status'],'cleaned bytes',report.get('bytes_deleted_verified',0),'items',report.get('deleted_count',0),flush=True)

if __name__=='__main__':main()
