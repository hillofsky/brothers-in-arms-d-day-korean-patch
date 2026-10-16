import importlib.util,csv,re,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();iso=Path('PROJECT_ROOT/BIA_STEP112_DIALOGUE_AND_INTERACTION_KO_TEST.iso');out=Path('outputs/step112');reports=[]
for row in csv.DictReader(Path('PROJECT_ROOT/translation/stage42b/movie_subtitles_ko.tsv').open(encoding='utf-8-sig'),delimiter='\t'):
 if row['field_index']!='1' or not(row['file'].startswith('EM_12') or row['file'].startswith('EM_13') or row['file'].startswith('FM_0115')):continue
 name=row['file'].replace('.ST1','.TI1');parts=['PSP_GAME','USRDIR','SYSTEM',name];_,old=b.iso_read_file(iso,parts);assert len(old)==512*512*4
 if name.startswith('FM_'):texts=['운명과의 만남','프랑스 생메르에글리즈 상공','D-Day 01:15  1944년 6월 6일']
 else:
  time=re.search(r'D\+15 (\d{2})(\d{2})',row['english']);assert time;texts=['에필로그','프랑스 셰르부르 인근',f'D+15 {time[1]}:{time[2]}  1944년 6월 21일']
 # Generate a native title-card asset from the translated UI text, same RGBA format/dimensions.
 im=Image.new('RGBA',(512,512),(0,0,0,255));draw=ImageDraw.Draw(im)
 for line,y,size in zip(texts,[108,131,149],[15,12,12]):
  font=ImageFont.truetype('LOCAL_PATH',size);box=draw.textbbox((0,0),line,font=font);w=box[2]-box[0];assert w<=360;draw.text((236-w/2-box[0],y-box[1]),line,font=font,fill=(235,235,235,255))
 titlefont=ImageFont.truetype('LOCAL_PATH',15);width=draw.textbbox((0,0),texts[0],font=titlefont)[2];draw.line((236-width/2,127,236+width/2,127),fill=(220,35,35,255),width=1)
 raw=im.tobytes();assert len(raw)==len(old);b.overwrite_iso_same_size(iso,parts,raw);assert b.iso_read_file(iso,parts)[1]==raw;im.save(out/(name+'.png'));reports.append({'resource':name,'translated_lines':texts,'same_dimensions_and_format':True,'iso_readback_verified':True})
(out/'movie_title_cards.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8');print('NATIVE TITLE CARDS',len(reports))
