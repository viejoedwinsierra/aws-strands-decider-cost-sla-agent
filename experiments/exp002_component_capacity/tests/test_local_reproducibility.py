from pathlib import Path
import os, tempfile, subprocess, json, re, ast, hashlib
root=Path(__file__).resolve().parents[1]
infra=root/'infrastructure'
for f in root.rglob('*.sh'):
 subprocess.run(['bash','-n',str(f)],check=True)
for f in root.rglob('*.py'):
 ast.parse(f.read_text(),filename=str(f))
print('PASS: bash syntax and Python parsing')
with tempfile.TemporaryDirectory() as tmp:
 tmp=Path(tmp)
 wheels=tmp/'wheels'; wheels.mkdir()
 (wheels/'fastapi-0.115.6-py3-none-any.whl').write_bytes(b'dummy')
 (wheels/'uvicorn-0.34.0-py3-none-any.whl').write_bytes(b'dummy')
 source=(infra/'prepare_dependencies.sh').read_text()
 lock_code=source.split("<<'PYLOCK'\n",1)[1].split('\nPYLOCK',1)[0]
 subprocess.run(['python3','-',str(wheels)],input=lock_code,text=True,check=True)
 assert (wheels/'requirements.lock').read_text()=='fastapi==0.115.6\nuvicorn==0.34.0\n'
 print('PASS: lockfile semantic test with two wheels')
 config=tmp/'experiment.env'; config.write_text('AWS_PROFILE=academy-sandbox\nEVIDENCE_BUCKET=bucket\n')
 config_code=source.split("<<'PYCONFIG'\n",1)[1].split('\nPYCONFIG',1)[0]
 subprocess.run(['python3','-'],input=config_code,text=True,check=True,env={**os.environ,'CONFIG_FILE':str(config),'HASH_KEY':'FASTAPI_BUNDLE_HASH','BUNDLE_HASH':'a'*64})
 assert len(config.read_text().splitlines())==3
 assert 'FASTAPI_BUNDLE_HASH='+'a'*64 in config.read_text().splitlines()
 print('PASS: config preservation and hash update')
 for name, vars in [('fastapi',{'APP_FILE':str(root/'exp002_fastapi/app/main.py'),'FASTAPI_BUNDLE_HASH':'a'*64,'RUN_ID':'test'}),('locust',{'LOCUST_FILE':str(root/'scripts/locustfile.py'),'LOCUST_BUNDLE_HASH':'b'*64})]:
  s=(infra/f'deploy_{name}.sh').read_text()
  py=s.split("<<'PYCODE'\n",1)[1].split('\nPYCODE',1)[0]
  out=tmp/f'{name}.json'
  env={**os.environ,**vars,'VALIDATOR_FILE':str(root/'scripts/verify_locked_environment.py'),'EVIDENCE_BUCKET':'example-bucket'}
  subprocess.run(['python3','-',str(out)],input=py,text=True,check=True,env=env)
  remote=json.loads(out.read_text())['commands'][0]
  remote_file=tmp/f'{name}.sh';remote_file.write_text(remote)
  subprocess.run(['bash','-n',str(remote_file)],check=True)
  assert 'requirements.lock' in remote and 'sha256sum -c SHA256SUMS.txt' in remote and 'verify_locked_environment.py' in remote
  assert ('a'*64 if name=='fastapi' else 'b'*64) in remote
  print(f'PASS: generated {name} SSM payload and remote shell syntax')
print('ALL LOCAL CHECKS PASS; no AWS calls')
