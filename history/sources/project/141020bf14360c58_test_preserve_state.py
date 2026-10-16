import pathlib,subprocess,tempfile,sys
root=pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as td:
    d=pathlib.Path(td);(d/'log').mkdir()
    initial='# Keep step 94\n\n<!-- STEP_095_MANAGED_BEGIN -->\nSTEP095 failed before result ZIP\n<!-- STEP_095_MANAGED_END -->\n'
    (d/'PROJECT_STATE.md').write_text(initial)
    run=d/'run';run.mkdir()
    script=root/'scripts'/'update_state.py'
    for phase in ('failure','success'):
        subprocess.check_call([sys.executable,str(script),'--root',str(d),'--runid','mock','--phase',phase,'--run-dir',str(run)])
    text=(d/'PROJECT_STATE.md').read_text()
    assert initial in text
    assert text.count('<!-- STEP_095_FIX2_MANAGED_BEGIN -->')==1
    assert (run/'PROJECT_STATE_BEFORE_STEP095_FIX2.md').read_text()==initial
    print('PASS: preceding STEP094/095 history untouched; managed block idempotent')
