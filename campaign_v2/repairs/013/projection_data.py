"""Preserve raw ext4 journal and original no-replay observation, then read an explicit replay derivative."""
import json,shlex,subprocess,tarfile,time
from pathlib import Path
from provision_vm import save,sha

def create_overlay(base,path):
 subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(base),str(path)],capture_output=True,check=True)

def extract(host,source,profile,out,events,*,original_expected_sha256):
 """No browser oracle. Original image remains QEMU read-only. Only a fresh derivative is journal-replayed."""
 out=Path(out);out.mkdir(exist_ok=False);helper=None
 before=sha(source)
 if before!=original_expected_sha256 or source.stat().st_mode&0o222:raise RuntimeError('Original view not immutable or hash-bound')
 raw_args=host.vm_args
 def args(*a,**kw):
  result=raw_args(*a,**kw)
  if kw.get('memory',a[4] if len(a)>4 else 6144)==1024:
   result+=['-device','pcie-root-port,id=replay-port,slot=3,chassis=3']
  return result
 host.vm_args=args
 try:
  boot=out/'journal-helper.qcow2';create_overlay(host.BASE,boot)
  helper=host.VM(boot,out/'journal-helper',2234,'journal-'+str(time.monotonic_ns()),events,memory=1024)
  helper.attach_evidence_after_boot(source)
  config={'device':'/dev/vdc','data_volume':True,'fstype':'ext4','profile':profile,'profile_relative':Path(profile).relative_to('/var/lib/idbv2').as_posix(),'output':'/tmp/idbv2-extract'}
  raw=host.remote(helper.port,'sudo /opt/idbv2/venv/bin/python /opt/idbv2/worker/guest_forensics.py',input=json.dumps(config).encode(),timeout=60,check=False)
  (out/'original-noload.stdout').write_bytes(raw.stdout);(out/'original-noload.stderr').write_bytes(raw.stderr)
  save(out/'ORIGINAL_NO_REPLAY_OBSERVATION.json',{'returncode':raw.returncode,'source_sha256':before,'requested_mount_options':'ro,noload','original_block_read_only':True,'view_kind':'original_no_replay','unavailable':raw.returncode!=0,'unavailable_reason':'bad_message_errno74' if b'[Errno 74] Bad message' in raw.stderr else 'missing_namespace' if raw.returncode else None})
  if raw.returncode and b'Evidence view missing expected IndexedDB directory' not in raw.stderr and b'[Errno 74] Bad message' not in raw.stderr:raise RuntimeError('Original extractor failed for an unrecognized reason; no projection')
  if raw.returncode==0:
   with (out/'original-no-replay-extract.tar').open('xb') as f:
    subprocess.run(host.ssh(helper.port)+['sudo tar -C /tmp/idbv2-extract -cf - .'],stdout=f,stderr=subprocess.PIPE,check=True,timeout=60)
   original_files=out/'original-forensics';original_files.mkdir()
   with tarfile.open(out/'original-no-replay-extract.tar') as tf:tf.extractall(original_files,filter='data')
   original_inventory=json.loads((original_files/'inventory.json').read_text())
   if not all(sha(original_files/'files'/x['relative_path'])==x['sha256'] for x in original_inventory['files']):raise RuntimeError('Original no-replay member hash mismatch')
  # Raw journal and filesystem headers are extracted directly from the unmounted, read-only original.
  for filename,args0 in [('original-ext4-stats', ['sudo','debugfs','-c','-R','stats','/dev/vdc']),('journal-inode', ['sudo','debugfs','-c','-R','stat <8>','/dev/vdc']),('journal-dump', ['sudo','debugfs','-c','-R','dump <8> /tmp/idbv2-journal.bin','/dev/vdc']),('e2fsck-version',['sudo','e2fsck','-V'])]:
   r=host.remote(helper.port,shlex.join(args0),timeout=60,check=False)
   (out/(filename+'.stdout')).write_bytes(r.stdout);(out/(filename+'.stderr')).write_bytes(r.stderr)
   save(out/(filename+'.response.json'),{'returncode':r.returncode,'command':args0})
   if r.returncode or b'Filesystem not open' in r.stderr:raise RuntimeError('Raw journal/tool inventory command failed '+filename)
  with (out/'original-journal.bin').open('xb') as f:
   subprocess.run(host.ssh(helper.port)+['sudo cat /tmp/idbv2-journal.bin'],stdout=f,stderr=subprocess.PIPE,check=True,timeout=60)
  journal=out/'original-journal.bin'
  with journal.open('rb') as f:header=f.read(12)
  if len(header)!=12 or int.from_bytes(header[:4],'big')!=0xc03b3998:raise RuntimeError('Raw JBD2 journal header unavailable/unsupported')
  save(out/'ORIGINAL_JOURNAL.json',{'bytes':journal.stat().st_size,'sha256':sha(journal),'header_hex':header.hex(),'source_sha256':before,'original_read_only':True,'no_browser_oracle':True})
  derivative=out/'journal-replay-derivative.qcow2';create_overlay(source,derivative)
  save(out/'DERIVATIVE_BEFORE.json',{'sha256':sha(derivative),'backing_source':str(source),'backing_sha256':before,'purpose':'explicit journal-only filesystem projection, not original raw state or endpoint oracle'})
  helper.qmp.execute('blockdev-add',{'driver':'qcow2','node-name':'replay-node','read-only':False,'file':{'driver':'file','filename':str(derivative),'cache':{'direct':True,'no-flush':False}}})
  helper.qmp.execute('device_add',{'driver':'virtio-blk-pci','drive':'replay-node','id':'replay-device','serial':'idbv2-projection','bus':'replay-port'})
  device_observations=[]
  end=time.monotonic()+15
  while time.monotonic()<end:
   r=host.remote(helper.port,'test -b /dev/vdd && cat /sys/block/vdd/ro /sys/block/vdd/serial',check=False)
   device_observations.append({'returncode':r.returncode,'stdout':r.stdout.decode(errors='replace'),'stderr':r.stderr.decode(errors='replace'),'host_ns':time.monotonic_ns()})
   save(out/('projection-device-observation-'+str(len(device_observations)).zfill(3)+'.json'),device_observations[-1])
   if r.returncode==0 and r.stdout.decode().splitlines()==['0','idbv2-projection']:break
   time.sleep(.1)
  else:raise RuntimeError('Fresh projection device identity not confirmed')
  if host.remote(helper.port,'findmnt -nr -S /dev/vdd',check=False).returncode==0:raise RuntimeError('Projection is already mounted; refuse fsck')
  started=time.monotonic_ns();cmd=['sudo','e2fsck','-p','-E','journal_only','/dev/vdd']
  r=host.remote(helper.port,shlex.join(cmd),timeout=60,check=False)
  (out/'journal-replay.stdout').write_bytes(r.stdout);(out/'journal-replay.stderr').write_bytes(r.stderr)
  save(out/'JOURNAL_REPLAY_RESPONSE.json',{'command':cmd,'returncode':r.returncode,'host_start_ns':started,'host_return_ns':time.monotonic_ns(),'device':'/dev/vdd','original_device':'/dev/vdc','replay_performed_on_derivative':True,'full_filesystem_repair_requested':False})
  if r.returncode not in [0,1]:raise RuntimeError('Journal-only replay did not pass; stop without full fsck workaround')
  helper.quit();helper=None
  if sha(source)!=before:raise RuntimeError('Original image changed during projection')
  derivative.chmod(0o444);projection_sha=sha(derivative)
  save(out/'DERIVATIVE_AFTER.json',{'sha256':projection_sha,'backing_sha256':before,'read_only_after_replay':True,'journal_replay_performed':True,'oracle_started':False})
  readboot=out/'projection-reader.qcow2';create_overlay(host.BASE,readboot)
  helper=host.VM(readboot,out/'projection-reader',2234,'projection-reader-'+str(time.monotonic_ns()),events,memory=1024)
  helper.attach_evidence_after_boot(derivative)
  r=host.remote(helper.port,'sudo /opt/idbv2/venv/bin/python /opt/idbv2/worker/guest_forensics.py',input=json.dumps(config).encode(),timeout=60,check=False)
  (out/'projection-extraction.stdout').write_bytes(r.stdout);(out/'projection-extraction.stderr').write_bytes(r.stderr)
  save(out/'PROJECTION_EXTRACTION_RESPONSE.json',{'returncode':r.returncode,'view_kind':'journal_replay_derivative','source_sha256':projection_sha,'original_source_sha256':before})
  if r.returncode:raise RuntimeError('Read-only derivative extraction unavailable; preserve and stop')
  with (out/'projection-extract.tar').open('xb') as f:
   subprocess.run(host.ssh(helper.port)+['sudo tar -C /tmp/idbv2-extract -cf - .'],stdout=f,stderr=subprocess.PIPE,check=True,timeout=60)
  helper.quit();helper=None
  files=out/'forensics';files.mkdir()
  with tarfile.open(out/'projection-extract.tar') as tf:tf.extractall(files,filter='data')
  inventory=json.loads((files/'inventory.json').read_text())
  if not inventory['files'] or not all(sha(files/'files'/v['relative_path'])==v['sha256'] for v in inventory['files']):raise RuntimeError('Derivative extract empty or hash mismatch')
  if not inventory['block_read_only'] or inventory['replay_performed'] or inventory['mount_options_requested']!='ro,noload':raise RuntimeError('Post-replay reader was not read-only/no-replay')
  if sha(source)!=before or sha(derivative)!=projection_sha:raise RuntimeError('Original or projection changed during reader')
  receipt={'view_kind':'journal_replay_derivative','original_source':str(source),'original_sha256':before,'projection_source':str(derivative),'projection_sha256':projection_sha,'raw_journal_sha256':sha(journal),'raw_no_replay_available':raw.returncode==0,'journal_replay_performed_on_separate_derivative':True,'post_replay_extract_read_only':True,'oracle_started':False,'files':len(inventory['files']),'callback_attribution':'not established','not_instantaneous_crash_state':True}
  save(out/'PROJECTION_RECEIPT.json',receipt);return receipt
 finally:
  if helper:helper.quit()
  host.vm_args=raw_args
