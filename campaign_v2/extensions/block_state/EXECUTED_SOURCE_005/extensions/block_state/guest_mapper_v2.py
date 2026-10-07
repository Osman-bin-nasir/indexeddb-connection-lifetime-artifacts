"""Matched mapped-volume provisioning and neutral mapper verification. No browser transaction or assigned fault."""
import json,mmap,os,subprocess,sys,time
from pathlib import Path
SIZE=1024**3;DATA='/dev/vdc';LOG='/dev/vdd';MAPPER='/dev/mapper/idbv2-browser'
def run(args):
 r=subprocess.run(args,capture_output=True,text=True);print(json.dumps({'kind':'MAPPER_COMMAND','argv':args,'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'guest_ns':time.monotonic_ns()}),flush=True)
 if r.returncode:raise RuntimeError('Mapper command failed '+repr(args))
 return r.stdout.strip()
def identity():
 if run(['findmnt','-nr','-o','SOURCE','/'])!='/dev/vda1':raise RuntimeError('Wrong isolated guest root')
 for dev,serial in [(DATA,'idbv2-data'),(LOG,'idbv2-log')]:
  if Path('/sys/block/'+Path(dev).name+'/serial').read_text().strip()!=serial or run(['blockdev','--getro',dev])!='0' or int(run(['blockdev','--getsize64',dev]))!=SIZE:raise RuntimeError('Data/log identity mismatch')
  result=subprocess.run(['blkid','-p',dev],capture_output=True,text=True)
  if result.returncode!=2 or result.stdout:raise RuntimeError('Device has old signature, refusing reuse')
  # QEMU blank input is also hash-bound by host; initial/terminal bytes must be zero.
  with open(dev,'rb',buffering=0) as f:
   if f.read(4096)!=bytes(4096):raise RuntimeError('Not blank')
   f.seek(SIZE-4096)
   if f.read(4096)!=bytes(4096):raise RuntimeError('Not blank')
def create(mapper):
 identity();sectors=SIZE//512
 if mapper=='linear_control':table=f'0 {sectors} linear {DATA} 0'
 elif mapper=='dm_log_writes':run(['modprobe','dm_log_writes']);table=f'0 {sectors} log-writes {DATA} {LOG}'
 elif mapper=='dm_flakey_drop_writes':run(['modprobe','dm_flakey']);table=f'0 {sectors} flakey {DATA} 0 3600 0'
 else:raise RuntimeError('Unknown registered mapper')
 run(['dmsetup','create','idbv2-browser','--table',table]);actual=run(['dmsetup','table','idbv2-browser']);run(['dmsetup','status','idbv2-browser'])
 print(json.dumps({'kind':'MAPPER_READY','mapper':mapper,'table_requested':table,'table_observed':actual,'data':DATA,'log':LOG,'size_bytes':SIZE,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'guest_ns':time.monotonic_ns(),'role':'support_only'}),flush=True)
def transition():
 start=time.monotonic_ns();run(['dmsetup','suspend','--noflush','idbv2-browser']);run(['dmsetup','reload','idbv2-browser','--table',f'0 {SIZE//512} flakey {DATA} 0 0 3600 1 drop_writes']);run(['dmsetup','resume','idbv2-browser']);table=run(['dmsetup','table','idbv2-browser'])
 print(json.dumps({'kind':'FLAKEY_TRANSITION','start_guest_ns':start,'end_guest_ns':time.monotonic_ns(),'table':table,'no_target_fsync':True}),flush=True)
def mark(name):run(['dmsetup','message','idbv2-browser','0','mark',name])
def write(offset,byte):
 a=mmap.mmap(-1,4096);a[:]=bytes([byte])*4096;fd=os.open(MAPPER,os.O_RDWR|os.O_DIRECT)
 try:
  n=os.pwrite(fd,a,offset);os.fsync(fd)
 finally:os.close(fd);a.close()
 backing_fd=os.open(DATA,os.O_RDONLY|os.O_DIRECT);buffer=mmap.mmap(-1,4096)
 try:
  count=os.preadv(backing_fd,[buffer],offset)
  if count!=4096:raise RuntimeError('Short independent direct backing read')
  actual=bytes(buffer)
 finally:os.close(backing_fd);buffer.close()
 print(json.dumps({'kind':'NEUTRAL_WRITE_WITNESS','offset':offset,'byte':byte,'returned':n,'backing_read_hex_prefix':actual[:16].hex(),'backing_all_matches':actual==bytes([byte])*4096,'guest_ns':time.monotonic_ns()}),flush=True)
 return actual

def main():
 c=json.loads(sys.stdin.read())
 if c.get('role') not in ['support','qualification'] or os.geteuid()!=0:raise RuntimeError('Explicit excluded role and isolated guest root required')
 mode=c['command']
 if mode=='create':create(c['mapper'])
 elif mode=='transition':transition()
 elif mode=='mark':mark(c['name'])
 elif mode=='neutral':
  create(c['mapper']);mapper=c['mapper']
  if mapper=='dm_log_writes':mark('neutral-before')
  a=write(0,0x41)
  if a!=b'A'*4096:raise RuntimeError('Healthy mapping did not persist neutral direct write')
  if mapper=='dm_log_writes':mark('neutral-ack')
  if mapper=='dm_flakey_drop_writes':transition()
  b=write(4096,0x42)
  if mapper=='dm_flakey_drop_writes':
   if b!=bytes(4096):raise RuntimeError('Drop-writes validation failed')
  elif b!=b'B'*4096:raise RuntimeError('Second healthy neutral write failed')
  if mapper=='dm_log_writes':mark('neutral-boundary')
  run(['dmsetup','status','idbv2-browser']);print(json.dumps({'kind':'NEUTRAL_MAPPER_PASS','mapper':mapper,'no_browser_or_target':True,'guest_ns':time.monotonic_ns()}),flush=True)
 else:raise RuntimeError('Unregistered tooling command')
if __name__=='__main__':main()
