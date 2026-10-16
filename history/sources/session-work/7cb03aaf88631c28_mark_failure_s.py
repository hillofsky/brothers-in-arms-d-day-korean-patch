from pathlib import Path
import json
out=Path('outputs/stage40s_validation');r={'status':'failed_runtime_validation','promote_iso':False,'test_iso':'PROJECT_ROOT/BIA_STAGE40S_FIRST_MISSION_KOREAN_TEST.iso','reason':'First mission load stopped on invalid 0x2a2a2a40 write at 0x08ca045c. No working campaign font or translation claim.','baseline_campaign_verified':'Stage40O entered first mission and pause menu.'};(out/'stage40s_failure_report.json').write_text(json.dumps(r,indent=2));print(r['reason'])
