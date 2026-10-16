exec(open('work/quit_y.py',encoding='utf-8-sig').read().split('try:')[0])
try:
 print(ws.request('input.buttons.send',buttons={x:False for x in ['start','down','up','cross','circle','left','right','square','triangle','select']},timeout=5));print(ws.request('input.analog.send',x=0,y=0,timeout=5));time.sleep(.2);print(ws.request('input.buttons.press',button='down',duration=20,timeout=8))
finally:ws.close()

