import json
from pathlib import Path
p=Path('outputs/stage43b/hud_font_inventory.json');d=json.loads(p.read_text(encoding='utf-8'));d['glyph_record_layout']='4 int32 metrics, 1 byte TextureIndex, 3 padding bytes; the last 4-byte word must not be interpreted as a pointer'
for g in d['glyphs']:
 v=int(g.pop('glyph_image_pointer'),0);g['texture_index']=v&255;g['padding_hex']=v.to_bytes(4,'little')[1:].hex()
p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
p=Path('outputs/bia_campaign_progress.md');s=p.read_text(encoding='utf-8');s+='\n추가 작업: Stage43D에서 게임용 글꼴을 기존 영문 150자와 한글 729자, 총 879자로 확장했습니다. 영문 텍스처를 유지하고 검증된 한글 텍스처를 두 번째 텍스처로 연결했습니다. 879개 문자 해시 조회, MDI 복원, ISO 읽기 검사를 통과했습니다. UTF-8 문자 소비 경로 수정과 실제 표시 검증은 아직 미완료입니다.\n\n이전 기록의 글자별 이미지 객체 해석을 정정합니다. 20바이트 글자 레코드의 끝 4바이트는 이미지 포인터가 아니라 1바이트 텍스처 번호와 3바이트 패딩입니다.\n';p.write_text(s,encoding='utf-8')
