from pathlib import Path
s=Path('work/audit_campaign_first.py').read_text(encoding='utf-8').replace('D0_0130_.MDI','D0_0700_.MDI').replace('first_campaign_units.json','campaign_second_units.json').replace('campaign_first_reference_audit.json','campaign_second_reference_audit.json');Path('work/audit_campaign_second.py').write_text(s,encoding='utf-8')
