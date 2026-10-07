"""Fresh dedicated data-volume provisioning, not scientific acquisition or qualification."""
import json,os,subprocess,sys,time
from pathlib import Path
DEVICE='/dev/vdc';SERIAL='idbv2-data';MOUNT='/var/lib/idbv2';SIZE=1024**3

def run(args,check=True):
 p=subprocess.run(args,text=True,capture_output=True)
 record={'command':args,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'guest_ns':time.monotonic_ns()};print(json.dumps({'kind':'VOLUME_COMMAND',**record}),flush=True)
 if check and p.returncode:raise RuntimeError('Volume command failed: '+repr(args))
 return p.stdout.strip()

def profile_options(filesystem):
 if filesystem=='ext4_commit30':return 'ext4',['-o','commit=30,discard'],'commit=30,discard'
 if filesystem=='ext4_defaults':return 'ext4',[],'defaults'
 if filesystem=='xfs_defaults':return 'xfs',[],'defaults'
 raise RuntimeError('Unregistered filesystem profile')

def main():
 c=json.loads(sys.stdin.read())
 if c.get('role') not in ['support','qualification']:raise RuntimeError('Build tooling refuses scientific acquisition')
 if os.geteuid()!=0:raise RuntimeError('Root required inside isolated guest')
 fs,options,fstab=profile_options(c['filesystem'])
 root=run(['findmnt','-nr','-o','SOURCE','/'])
 if root!='/dev/vda1':raise RuntimeError('Unexpected root identity')
 serial=Path('/sys/block/vdc/serial').read_text().strip()
 if serial!=SERIAL or run(['blockdev','--getro',DEVICE])!='0':raise RuntimeError('Wrong dedicated writable data device')
 if int(run(['blockdev','--getsize64',DEVICE]))!=SIZE:raise RuntimeError('Wrong matched data-volume size')
 mounts=json.loads(run(['findmnt','-J']))
 def sources(items):
  for i in items:
   yield i.get('source','')
   yield from sources(i.get('children',[]))
 if DEVICE in set(sources(mounts['filesystems'])):raise RuntimeError('Data device already mounted')
 existing=subprocess.run(['blkid','-p',DEVICE],capture_output=True,text=True)
 print(json.dumps({'kind':'PRIOR_SIGNATURE','returncode':existing.returncode,'stdout':existing.stdout,'stderr':existing.stderr}),flush=True)
 if existing.returncode!=2 or existing.stdout.strip():raise RuntimeError('Not a fresh blank volume; refusing format/reuse')
 run(['mkfs.ext4','-F',DEVICE] if fs=='ext4' else ['mkfs.xfs','-f',DEVICE])
 Path(MOUNT).mkdir(parents=True,exist_ok=True)
 if any(Path(MOUNT).iterdir()):raise RuntimeError('Data mount point contains prior evidence')
 run(['mount','-t',fs,*options,DEVICE,MOUNT])
 # Auxiliary source is exact device path, after serial/size identity checks.
 line=f'{DEVICE} {MOUNT} {fs} {fstab} 0 '+('2' if fs=='ext4' else '0')+'\n'
 old=Path('/etc/fstab').read_text()
 if any(MOUNT in row.split()[1:2] for row in old.splitlines() if row.strip() and not row.lstrip().startswith('#')):raise RuntimeError('Existing data fstab entry; refusing replacement')
 with Path('/etc/fstab').open('a') as f:f.write(line);f.flush();os.fsync(f.fileno())
 run(['chown','research:research',MOUNT])
 identity={'kind':'DATA_VOLUME_READY','role':c['role'],'filesystem_requested':c['filesystem'],'fstype':fs,'mount_arguments':['mount','-t',fs,*options,DEVICE,MOUNT],'fstab_added':line,'actual_mount':json.loads(run(['findmnt','-J',MOUNT])),'filesystem_identity':run(['blkid','-p',DEVICE]),'root_mount':json.loads(run(['findmnt','-J','/'])),'data_serial':serial,'data_size_bytes':SIZE,'root_device':root,'data_device':DEVICE,'guest_ns':time.monotonic_ns(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'sysctls_unchanged':{n:Path('/proc/sys/vm/'+n).read_text().strip() for n in ['dirty_writeback_centisecs','dirty_expire_centisecs','dirty_ratio','dirty_background_ratio']}}
 print(json.dumps(identity),flush=True)
if __name__=='__main__':main()
