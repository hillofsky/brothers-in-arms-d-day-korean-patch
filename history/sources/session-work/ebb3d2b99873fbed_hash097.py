import hashlib,json
from pathlib import Path
s=Path('PROJECT_ROOT/BIA_STAGE79_COMPILED967_STRUCTURAL_TEST.iso');h=hashlib.file_digest(s.open('rb'),'sha256').hexdigest();assert h=='ca320d514c32d34767e7255ea3079f7449783cdb2b98ec49797a87bdd69544d9';p=Path('outputs/step097/build_report.json');d=json.loads(p.read_text());d['source_sha256_verified']=h;d['output_sha256']=hashlib.file_digest(Path(d['output']).open('rb'),'sha256').hexdigest();p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');print('SOURCE HASH PRESERVED',h)
