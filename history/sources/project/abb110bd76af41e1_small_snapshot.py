#!/usr/bin/env python3
"""Read-only post-screenshot snapshot. Never assumes a former PSP RAM address is stable."""
import argparse,datetime,json,struct,hashlib,traceback
from pathlib import Path
from ws_readonly import WS,memread

def word(b,o=0):return struct.unpack_from('<I',b,o)[0]
def h(n):return f'0x{n:08X}'

def snapshot(ws):
    result={'sampled_at':datetime.datetime.now().astimezone().isoformat(),
            'note':'Historical addresses are not validated in the current run; zero means absent/stale, not a writer.',
            'read_only':True,'memory_bytes_total':0,'results':{}}
    result['version']=ws.request('version',8,name='bia095-fix3',version='1.0')
    result['game_status']=ws.request('game.status',8)
    for label,address,size in [('historical_owner',0x09A69A90,0x38),('historical_font',0x09A74150,0x60),('historical_korean_utf8',0x09E7B040,0x60)]:
        try:
            b=memread(ws,address,size); result['memory_bytes_total']+=len(b)
            row={'address':h(address),'sha256':hashlib.sha256(b).hexdigest(), 'first_64_hex':b[:64].hex(),'all_zero':not any(b)}
            if label=='historical_owner':
                row.update({'vtable':h(word(b)),'font_ptr_plus_0x28':h(word(b,0x28)),
                            'vtable_matches_prior':word(b)==0x08D67A88,
                            'font_matches_prior':word(b,0x28)==0x09A74150})
            if label=='historical_font':row.update({'glyph_count_plus_0x44':word(b,0x44),'records_ptr_plus_0x40':h(word(b,0x40))})
            if label=='historical_korean_utf8':
                row.update({'contains_known_phrase':('프랑스 유타 해변 인근'.encode('utf8') in b),
                            'prefix_utf8':b.split(b'\x00')[0][:90].decode('utf8','replace')})
            result['results'][label]=row
        except Exception as e:result['results'][label]={'address':h(address),'error':repr(e)}
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out);ws=None
    try:
        ws=WS(a.port);data=snapshot(ws)
        out.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf8')
    except Exception:
        out.write_text(json.dumps({'read_only':True,'status':'SNAPSHOT_ERROR','traceback':traceback.format_exc()},indent=2),encoding='utf8')
        raise
    finally:
        if ws:ws.close()
if __name__=='__main__':main()
