#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage081: verified main menu -> Story submenu -> selected New Game.

Uses dedicated, owner-verified PPSSPP WebSocket provided by run.ps1.
Never claims mission text render based on RAM bytes alone.
"""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
import time
import traceback
from pathlib import Path
import stage071_known_good as kg

EXPECTED_ISO_SHA='ca320d514c32d34767e7255ea3079f7449783cdb2b98ec49797a87bdd69544d9'
EXPECTED_GAME='ULUS10193'


def dump(path, val):
    Path(path).write_text(json.dumps(val,ensure_ascii=False,indent=2),encoding='utf-8')


def gray_count(rgb,box):
    x0,y0,x1,y1=box
    result=0
    for y in range(y0,y1):
        base=y*kg.W*3
        for x in range(x0,x1):
            pos=base+x*3
            r,g,b=rgb[pos:pos+3]
            if min(r,g,b)>115 and max(r,g,b)-min(r,g,b)<30:
                result+=1
    return result


def capture(ws,out,label,signatures):
    kg.pause(ws)
    try:
        output=[]
        for n,addr in enumerate(kg.VRAMS):
            data=kg.memread(ws,addr,kg.VRAM_SIZE)
            pixels=kg.rgb565(data)
            name=f'{label}_vram{n}_{addr:08X}.png'
            kg.savepng(out/name,pixels)
            score={k:kg.similarity(pixels,s) for k,s in signatures.items()}
            center=gray_count(pixels,(206,59,270,90))
            new_game=gray_count(pixels,(190,126,301,158))
            # Proven on actual Step080 screenshots: main: center 293/new game 27;
            # story submenu: center 0/new game 247. Use deliberately wide margins.
            if kg.matches(score['title']):
                state='TITLE'
            elif center>75 and new_game<90:
                state='MAIN_STORY_SELECTED'
            elif center<35 and new_game>105:
                state='STORY_SUBMENU_NEW_GAME_SELECTED'
            else:
                state='OTHER'
            output.append({
                'file':name,'buffer':n,'raw_sha256':hashlib.sha256(data).hexdigest(),
                'state':state,'main_story_bright_pixels':center,
                'new_game_bright_pixels':new_game,
                'known_signatures':score,
            })
        return output
    finally:
        kg.resume(ws)


def recognized(caps,state):
    return any(x['state']==state for x in caps)


def boot_game(ws,report):
    for i in range(90):
        g=ws.request('game.status',5)
        if g.get('game'):
            report['game']=g['game']
            if g['game'].get('id') != EXPECTED_GAME:
                raise RuntimeError('Wrong PSP game; refusing input '+repr(g))
            return
        time.sleep(.4)
    raise RuntimeError('No loaded PSP game reported')


def scan(ws,targets,out,label):
    r=kg.scan_targets(ws,targets)
    dump(out/f'{label}_ram_hits.json',r)
    return {'loaded_ids':[k for k,v in r.items() if v['loaded']],
            'file':f'{label}_ram_hits.json'}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--port',type=int,required=True)
    ap.add_argument('--outdir',required=True)
    ap.add_argument('--signatures',required=True)
    ap.add_argument('--canaries',required=True)
    ap.add_argument('--step079-evidence',required=True)
    ap.add_argument('--isolated-memstick',required=True)
    args=ap.parse_args()
    out=Path(args.outdir)
    out.mkdir(parents=True,exist_ok=True)
    signs=json.loads(Path(args.signatures).read_text(encoding='utf-8-sig'))
    targets=json.loads(Path(args.canaries).read_text(encoding='utf-8-sig'))['targets']
    ev=json.loads(Path(args.step079_evidence).read_text(encoding='utf-8-sig'))
    if ev.get('status')!='BUILT_UNVERIFIED' or ev.get('output_sha256')!=EXPECTED_ISO_SHA:
        raise RuntimeError('Bundled STEP079 evidence does not match target ISO')
    # Caller created a unique empty test-only memstick. Do not operate on real saves.
    memstick=Path(args.isolated_memstick)
    if not memstick.is_dir() or 'STEP_081' not in str(memstick).upper():
        raise RuntimeError('Dedicated STEP081 memory stick missing / invalid')

    report={
        'step':'STEP_081', 'status':'IN_PROGRESS',
        'target_iso_sha256':EXPECTED_ISO_SHA,
        'game_id_expected':EXPECTED_GAME,
        'isolated_memstick':str(memstick),
        'original_save_data_touched':False,
        'old_step080_false_negative_fixed':True,
        'compiled967_static_applied':True,
        'compiled967_visual_runtime_verified':False,
        'int92_visual_runtime_verified':False,
        'six_deferred_movie_playbacks_tested':False,
        'first_mission_runtime_previously_verified':True,
        'first_mission_runtime_this_run_verified':False,
        'new_game_selected_by_verified_story_submenu':False,
        'mission_started_visually_verified':False,
        'notes':'New Game entry can show a cutscene/another menu. Screenshots and RAM are evidence, not automatic proof of localized dialog rendering.'
    }
    ws=None
    checkpoint='connect'
    try:
        for attempt in range(80):
            try:
                ws=kg.WS(args.port)
                break
            except OSError:
                time.sleep(.5)
        if ws is None:
            raise RuntimeError('No dedicated PPSSPP WebSocket on verified port')
        report['version']=ws.request('version',8,name='bia-step081',version='1.0')
        checkpoint='game'
        boot_game(ws,report)
        print('[GAME] exact BIA game ID verified',flush=True)
        time.sleep(2)

        checkpoint='title_and_main'
        found_title=False
        for i in range(20):
            caps=capture(ws,out,f'00_boot_{i:02d}',signs)
            report.setdefault('boot_captures',[]).append(caps)
            if recognized(caps,'TITLE'):
                found_title=True
                break
            if recognized(caps,'MAIN_STORY_SELECTED'):
                # Title flashed too quickly, but menu itself is proven.
                break
            kg.tap(ws,'start',.2,.65)
        report['title_observed']=found_title
        if not recognized(caps,'MAIN_STORY_SELECTED'):
            kg.tap(ws,'start',.24,.7)
            for i in range(35):
                caps=capture(ws,out,f'01_main_seek_{i:02d}',signs)
                report.setdefault('main_seek',[]).append(caps)
                if recognized(caps,'MAIN_STORY_SELECTED'):
                    break
                time.sleep(.35)
        if not recognized(caps,'MAIN_STORY_SELECTED'):
            raise RuntimeError('Main menu Story selection could not be established; no blind input')
        report['main_menu_story_selected_verified']=True
        print('[MAIN] Story item selected, exact central title confirmed',flush=True)

        checkpoint='open_story_submenu'
        kg.tap(ws,'cross',.22,.75)
        for i in range(16):
            caps=capture(ws,out,f'02_story_submenu_{i:02d}',signs)
            report.setdefault('submenu_seek',[]).append(caps)
            if recognized(caps,'STORY_SUBMENU_NEW_GAME_SELECTED'):
                break
            time.sleep(.3)
        if not recognized(caps,'STORY_SUBMENU_NEW_GAME_SELECTED'):
            raise RuntimeError('Story submenu New Game not confirmed; refusal to select blindly')
        report['story_submenu_verified']=True
        report['new_game_selection_visible']=True
        print('[STORY] Story submenu and highlighted NEW GAME confirmed',flush=True)
        dump(out/'step081_report_partial.json',report)

        checkpoint='select_new_game'
        # Known screenshot: New Game is already highlighted after Story CROSS.
        # --memstick isolates all savedata so no real profile can be overwritten.
        kg.tap(ws,'cross',.26,.95)
        report['new_game_selected_by_verified_story_submenu']=True
        print('[NEW GAME] Pressed CROSS on highlighted New Game using isolated memstick',flush=True)

        checkpoint='post_new_game_capture'
        timeline=(0,1,3,5,8,12,18,25,35,50,70)
        t0=time.monotonic()
        captures=[]
        for i,t in enumerate(timeline):
            wait=t-(time.monotonic()-t0)
            if wait>0:time.sleep(wait)
            caps=capture(ws,out,f'03_new_game_{i:02d}_t{t:02d}s',signs)
            classes=[a['state'] for a in caps]
            record={'second':t,'states':classes,'images':[a['file'] for a in caps],
                    'main_story_bright_pixels':[a['main_story_bright_pixels'] for a in caps],
                    'new_game_bright_pixels':[a['new_game_bright_pixels'] for a in caps],
                    'raw_hashes':[a['raw_sha256'] for a in caps]}
            captures.append(record)
            report['post_new_game_frames']=captures
            dump(out/'step081_report_partial.json',report)
            print(f'[FRAME t={t}s] {classes}',flush=True)
            # Read-only RAM scan after actual new-game selection, not during all 11 frames.
            if t in (25,70):
                report[f'canaries_t{t}']=scan(ws,targets,out,f'game_t{t}')
                dump(out/'step081_report_partial.json',report)

        report['post_new_game_frames']=captures
        moved=any('OTHER' in x['states'] or 'TITLE' in x['states'] or 'MAIN_STORY_SELECTED' in x['states'] for x in captures)
        unchanged=all('STORY_SUBMENU_NEW_GAME_SELECTED' in x['states'] for x in captures)
        report['left_story_submenu'] = not unchanged
        if unchanged:
            report['status']='NEW_GAME_SELECTED_BUT_SUBMENU_NOT_LEFT'
        elif moved:
            report['status']='NEW_GAME_NEXT_SCREEN_CAPTURED_VISUAL_REVIEW'
        else:
            report['status']='NEW_GAME_NEXT_SCREEN_UNCLASSIFIED'
        # No unverified auto navigation beyond this checkpoint. A difficulty
        # dialog/movie/new profile screen must be assessed from screenshot.
        print(f"[DONE] {report['status']}",flush=True)
        checkpoint='complete'
    except Exception as e:
        report['status']='FAILED'
        report['failed_checkpoint']=checkpoint
        report['failure']=repr(e)
        report['traceback']=traceback.format_exc()
        raise
    finally:
        if ws:
            try:ws.close()
            except Exception:pass
        report['completed_at']=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
        dump(out/'step081_runtime_report.json',report)

if __name__=='__main__':main()
