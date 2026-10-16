#!/usr/bin/env python3
"""Read-only glyph/font register evidence, on the user-confirmed broken Mission 2 screen.

Exec logging uses PPSSPP conditional log breakpoints (no stepping and no memory writes).
Only install when no pre-existing breakpoint exists at monitored addresses.
"""
import argparse, datetime, json, time, traceback, re
from pathlib import Path
import stage071_known_good as kg

MARK='프랑스 유타 해변 인근'.encode('utf-8')
TARGETS=[
 ('glyph_lookup_codepoint',0x089F4178,
  'a1 == 0xD504 || a1 == 0x003E || a1 == 0xFFFD',
  'STEP088_LOOKUP cp={a1:x} font={a0:x} count={[a0+0x2c]:x} hashCount={[a0+0x54]:x} hashPtr={[a0+0x4c]:x} glyphPtr={[a0+0x28]:x} ra={ra:x}'),
 ('text_font_context',0x089F5668,
  'a1 >= 0x08000000 && a1 < 0x0A000000',
  'STEP088_CONTEXT font={a1:x} state={a0:x} aux={a2:x} fontHashCount={[a1+0x54]:x} fontGlyphs={[a1+0x2c]:x} ra={ra:x}'),
 ('utf8_dispatch_mission2',0x089F5704,
  'a0 >= 0x09E7B040 && a0 < 0x09E7B05F',
  'STEP088_DECODE src={a0:x} activeFont={s3:x} b0={[a0,1]:x} ra={ra:x}'),
]

def save(out,report):
 (out/'step088_register_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 (out/'STEP_088.md').write_text('# BIA STEP 088 — Mission 2 font argument trace\n\n'
   +f"Status: {report.get('status')}\n\n"
   +f"Runtime hits: {[(x['name'],x.get('hits')) for x in report.get('last_hits',[])]}\n\n"
   +f"Captured log samples: {len(report.get('sampled_register_logs',[]))}\n\n"
   +'No ISO, save, or emulated RAM writes. Do not classify translated game as fixed.\n',encoding='utf-8')

def verify_scene(ws):
 data=kg.memread(ws,0x09E7B040,len(MARK))
 if data!=MARK:raise RuntimeError('MISSION2_UTF8_ANCHOR_NOT_MATCHED: '+data.hex())
 before=kg.memread(ws,0x09E7B034,12)
 if not before.startswith(b'D-Day 06:00'):raise RuntimeError('MISSION2_TIME_ANCHOR_NOT_MATCHED: '+repr(before))
 return {'address':'0x09E7B040','utf8':data.decode(),'time':before.decode('ascii','replace')}

def bp_list(ws):
 return ws.request('cpu.breakpoint.list',10).get('breakpoints',[])

def do_probe(ws,report):
 # Safeguard: avoid modifying any user's existing CPU breakpoints.
 preexisting=bp_list(ws)
 report['preexisting_cpu_breakpoints']=preexisting[:50]
 for name,addr,condition,format_text in TARGETS:
  if any(x.get('address')==addr for x in preexisting):
   raise RuntimeError('PREEXISTING_CPU_BREAKPOINT_AT_'+hex(addr))
 added=[]
 try:
  report['cpu_before']=ws.request('cpu.status',10)
  if report['cpu_before'].get('stepping'):raise RuntimeError('CPU_PREEXISTING_PAUSED')
  for name,addr,condition,logfmt in TARGETS:
   response=ws.request('cpu.breakpoint.add',10,address=addr,enabled=False,log=True,
                       condition=condition,logFormat=logfmt)
   added.append((name,addr))
   report.setdefault('installed',[]).append({'name':name,'address':hex(addr),'condition':condition,'logFormat':logfmt,'response':response})
  samples=[]
  for i in range(6):
   time.sleep(.5)
   bps=bp_list(ws)
   status=ws.request('cpu.status',10)
   hits=[]
   for name,addr,_,_ in TARGETS:
    entry=next((x for x in bps if x.get('address')==addr),None)
    hits.append({'name':name,'address':hex(addr),'found':entry is not None,'hits':entry.get('hits') if entry else None})
   samples.append({'elapsed_seconds':(i+1)*.5,'stepping':status.get('stepping'),'hits':hits})
   if status.get('stepping'):raise RuntimeError('UNEXPECTED_CPU_PAUSE')
  report['samples']=samples
  report['last_hits']=samples[-1]['hits']
  report['cpu_after']=ws.request('cpu.status',10)
  report['sampled_register_logs']=getattr(ws,'diagnostic_logs',[])[:250]
  report['dropped_logs']=getattr(ws,'diagnostic_log_dropped',0)
  labels={}
  for entry in report['sampled_register_logs']:
   m=re.search('STEP088_(LOOKUP|CONTEXT|DECODE)',entry.get('message',''))
   if m:labels[m.group(1)]=labels.get(m.group(1),0)+1
  report['captured_log_types']=labels
  report['limitations']='Log sample capped; no-hit can be caused by rare codepath, debugger filters, or prior one-time lookup. The trace is diagnostic, not a fix.'
 finally:
  report['breakpoint_removal']=[]
  for name,addr in reversed(added):
   try:
    ws.request('cpu.breakpoint.remove',10,address=addr)
    report['breakpoint_removal'].append({'name':name,'removed':True})
   except Exception as e:
    report['breakpoint_removal'].append({'name':name,'removed':False,'error':str(e)})

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--port',required=True,type=int)
 p.add_argument('--output',required=True)
 p.add_argument('--expected',required=True)
 p.add_argument('--listener-pid',required=True,type=int)
 a=p.parse_args()
 out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
 report={'step':'STEP_088','status':'RUNNING','iso_modified':False,'psp_ram_writes':False,
         'read_only_game_memory':True,'pid_prechecked_by_launcher':a.listener_pid,
         'mission2_korean_render_fixed':False,'mode':'nonpausing filtered instruction logging'}
 ws=None
 try:
  ws=kg.WS(a.port)
  report['version']=ws.request('version',10,name='bia-step088-fontargs',version='1.0')
  game=ws.request('game.status',10)
  if game.get('game',{}).get('id')!='ULUS10193':raise RuntimeError('GAME_ID_MISMATCH')
  report['game_status']=game
  report['scene_anchor']=verify_scene(ws)
  do_probe(ws,report)
  report['status']='ARGUMENT_TRACE_COLLECTED_UNVERIFIED'
  print('Trace finished',report.get('last_hits'),flush=True)
 except Exception as ex:
  report['status']='FAILED';report['error']=str(ex);report['traceback']=traceback.format_exc()
  raise
 finally:
  if ws:
   try:ws.close()
   except Exception:pass
  report['completed_at']=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
  save(out,report)
if __name__=='__main__':main()
