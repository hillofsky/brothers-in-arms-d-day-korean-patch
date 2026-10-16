#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STEP080: isolated PPSSPP static-build runtime smoke, using proven STEP071 WS/VRAM code."""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
import time
import traceback
from pathlib import Path

import stage071_known_good as kg

ISO_SHA="ca320d514c32d34767e7255ea3079f7449783cdb2b98ec49797a87bdd69544d9"
GAME_ID="ULUS10193"

def save_json(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")

def cap_summary(caps,sigs):
    summ={}
    for label in sigs:
        ranks=[x["similarity"][label] for x in caps]
        summ[label]={
            "matched": kg.cap_matches(caps,label),
            "best_mae": min(x["mae"] for x in ranks),
            "best_close_ratio":max(x["close_ratio"] for x in ranks),
        }
    summ["raw_hashes"]=[x["raw_sha256"] for x in caps]
    return summ

def safe_status(ws):
    try:return ws.request("cpu.status",5)
    except Exception as e:return {"error":repr(e)}

def ram_snapshot(ws,targets,out,label):
    print(f"[RAM] {label}: reading 32 MiB read-only PSP RAM",flush=True)
    result=kg.scan_targets(ws,targets)
    loaded=[k for k,v in result.items() if v["loaded"]]
    save_json(out/f"{label}_canary_ram_hits.json",result)
    return {
        "loaded_ids":loaded,
        "loaded_count":len(loaded),
        "hits_file":f"{label}_canary_ram_hits.json",
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--port",type=int,required=True)
    ap.add_argument("--outdir",required=True)
    ap.add_argument("--signatures",required=True)
    ap.add_argument("--canaries",required=True)
    ap.add_argument("--step079-evidence",required=True)
    args=ap.parse_args()

    out=Path(args.outdir);out.mkdir(parents=True,exist_ok=True)
    sigs=json.loads(Path(args.signatures).read_text(encoding="utf-8-sig"))
    targets=json.loads(Path(args.canaries).read_text(encoding="utf-8-sig"))["targets"]
    build=json.loads(Path(args.step079_evidence).read_text(encoding="utf-8-sig"))
    if build.get("status")!="BUILT_UNVERIFIED" or build.get("output_sha256")!=ISO_SHA:
        raise RuntimeError("Bundled STEP079 evidence mismatch")

    ws=None
    report={
        "step":"STEP_080",
        "status":"IN_PROGRESS",
        "iso_sha256_expected":ISO_SHA,
        "target_game_id_expected":GAME_ID,
        "capture_method":"PROVEN_STEP071_RAW_VRAM_RGB565_SOFTWARE_RENDERER",
        "debugger_local_only":True,
        "compiled967_static_built":True,
        "compiled967_runtime_verified":False,
        "int92_runtime_verified":False,
        "six_deferred_movie_playback_tests_resumed":False,
        "no_iso_modified":True,
        "visual_review_required":True,
        "notes":"RAM text presence is not proof of rendered Korean. Story entry does not constitute movie playback validation.",
    }
    current="start"
    try:
        last=None
        for i in range(60):
            try:
                ws=kg.WS(args.port)
                break
            except Exception as e:
                last=e
                time.sleep(.5)
        if ws is None:
            raise RuntimeError(f"Could not connect to dedicated PPSSPP debugger at port {args.port}: {last}")

        report["version"]=ws.request("version",10,name="bia-step080",version="1.0")
        current="game_boot"
        for i in range(90):
            g=ws.request("game.status",5)
            if g.get("game"):
                report["game"]=g["game"]
                break
            time.sleep(.4)
        if "game" not in report:
            raise RuntimeError("PPSSPP did not report a booted game")
        if report["game"].get("id") != GAME_ID:
            raise RuntimeError(f"Wrong game ID; refusing input. Actual={report['game']}")
        print("[GAME] Exact BIA ULUS10193 booted",flush=True)

        current="title_seek"
        time.sleep(3)
        for i in range(15):
            cap=kg.capture(ws,out,f"00_title_seek_{i:02d}",sigs)
            report.setdefault("title_seek",[]).append({
                "attempt":i,"images":[x["file"] for x in cap],
                "signature":cap_summary(cap,sigs),
            })
            if kg.cap_matches(cap,"title"):
                report["title_verified_by_known_signature"]=True
                print(f"[TITLE] Matched previously verified signature, attempt={i}",flush=True)
                break
            kg.tap(ws,"start",.20,1.0)
        else:
            raise RuntimeError("Known BIA title screen not found; screenshot evidence captured")

        current="menu_wait"
        kg.tap(ws,"start",.22,.65)
        for i in range(30):
            cap=kg.capture(ws,out,f"01_menu_wait_{i:02d}",sigs)
            report.setdefault("menu_seek",[]).append({
                "poll":i,"images":[x["file"] for x in cap],
                "signature":cap_summary(cap,sigs),
            })
            if kg.cap_matches(cap,"menu_story"):
                report["main_menu_story_selected_verified"]=True
                print(f"[MENU] Known Story-selected main menu matched, poll={i}",flush=True)
                break
            time.sleep(.35)
        else:
            raise RuntimeError("Known BIA main menu with Story selected not found")

        current="menu_ram"
        report["canaries_at_main_menu"]=ram_snapshot(ws,targets,out,"menu")
        save_json(out/"step080_runtime_report_partial.json",report)

        # The Story selection is visually verified above. Only this known
        # item is confirmed; we never send guessed mission-selection sequences.
        current="story_entry"
        kg.tap(ws,"cross",.24,.9)
        timeline=(0,2,4,6,9,12,16,22,30)
        story_caps=[]
        start=time.monotonic()
        for idx,t in enumerate(timeline):
            remaining=t-(time.monotonic()-start)
            if remaining>0:
                time.sleep(remaining)
            cap=kg.capture(ws,out,f"02_story_{idx:02d}_t{t:02d}s",sigs)
            rec={
                "seconds_after_confirm_target":t,
                "images":[x["file"] for x in cap],
                "signature":cap_summary(cap,sigs),
            }
            story_caps.append(rec)
            save_json(out/"step080_runtime_report_partial.json",report|{
                "story_timeline":story_caps,
                "last_checkpoint":f"story_t{t}s",
            })
            print(f"[STORY] Capture at t={t}s; menu_story={rec['signature']['menu_story']['matched']}",flush=True)

        report["story_timeline"]=story_caps
        report["story_entry_left_menu_at_least_once"]=any(
            not x["signature"]["menu_story"]["matched"] for x in story_caps
        )
        report["canaries_after_story_entry"]=ram_snapshot(ws,targets,out,"story")
        before=set(report["canaries_at_main_menu"]["loaded_ids"])
        after=set(report["canaries_after_story_entry"]["loaded_ids"])
        report["canaries_newly_in_ram_after_story_entry"]=sorted(after-before)
        report["canaries_new_in_ram_count"]=len(after-before)
        report["cpu_status_after_story"]=safe_status(ws)

        # Conservative result: only boot/title/menu can be verified by the
        # known visual signatures. New Korean scene rendering is unverified.
        if report["story_entry_left_menu_at_least_once"]:
            report["status"]="TITLE_MENU_VERIFIED_STORY_TRANSITION_CAPTURED"
        else:
            report["status"]="TITLE_MENU_VERIFIED_STORY_NOT_CONFIRMED"

        print(f"[COMPLETE] {report['status']}; newly loaded RAM canaries={len(after-before)}",flush=True)
        current="complete"
    except Exception as e:
        report["status"]="FAILED"
        report["failed_checkpoint"]=current
        report["failure"]=str(e)
        report["traceback"]=traceback.format_exc()
        raise
    finally:
        if ws:
            try:ws.close()
            except Exception:pass
        report["completed_at"]=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        save_json(out/"step080_runtime_report.json",report)

if __name__=="__main__":
    main()
