"""Excluded-qualification fault dispatcher; stdin commands, no scientific endpoint logic."""
from __future__ import annotations
import json,os,pathlib,signal,sys,time,re

def emit(kind,**value):
 print(json.dumps({'kind':kind,'guest_monotonic_ns':time.monotonic_ns(),'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),**value}),flush=True)

def process(pid):
 p=pathlib.Path('/proc')/str(pid)
 try:
  raw=(p/'stat').read_text();fields=raw[raw.rindex(')')+2:].split();exe=os.readlink(p/'exe');cmd=(p/'cmdline').read_bytes().split(b'\0')
  return {'pid':pid,'state':fields[0],'ppid':int(fields[1]),'pgrp':int(fields[2]),'session':int(fields[3]),'start_ticks':int(fields[19]),'exe':exe,'cmdline':[s.decode(errors='replace') for s in cmd if s], 'cmdline_hex':(p/'cmdline').read_bytes().hex()}
 except (OSError,ValueError):return None

def inventory():
 return {r['pid']:r for p in pathlib.Path('/proc').iterdir() if p.name.isdecimal() and (r:=process(int(p.name))) is not None}

def has_profile(record,profile):
 # This packaged binary rewrites argv into one process-title string. Accept only
 # an exact option value bounded by argument/whitespace boundaries, never a prefix.
 if not re.fullmatch(r'/var/lib/idbv2/[A-Za-z0-9_-]+/profile',profile):raise RuntimeError('Unsafe profile identity')
 pattern=r'(?:^|\s)--user-data-dir='+re.escape(profile)+r'(?=\s|$)'
 return any(re.search(pattern,s) for s in record['cmdline'])

def has_process_type(record):
 return any(re.search(r'(?:^|\s)--type(?:=|\s)',s) for s in record['cmdline'])

def select_tree(records,profile,exe):
 roots=[r for r in records.values() if r['exe']==exe and has_profile(r,profile) and not has_process_type(r)]
 if len(roots)!=1:raise RuntimeError('Browser root identity is not unique')
 root=roots[0];selected={root['pid']}
 while True:
  new={r['pid'] for r in records.values() if r['ppid'] in selected}
  if new<=selected:break
  selected.update(new)
 groups={records[p]['pgrp'] for p in selected}
 if any(g<=1 for g in groups):raise RuntimeError('Unsafe process group')
 outsiders=[r['pid'] for r in records.values() if r['pgrp'] in groups and r['pid'] not in selected]
 if outsiders:raise RuntimeError('Selected process group includes outsiders: '+str(outsiders))
 if os.getpgrp() in groups:raise RuntimeError('Fault dispatcher shares browser group')
 return {'root_pid':root['pid'],'processes':[records[p] for p in sorted(selected)],'groups':sorted(groups)}

def dispatch_sigkill(profile,exe):
 tree=select_tree(inventory(),profile,exe)
 emit('SIGKILL_SELECTED_TREE',tree=tree)
 signals=[]
 for pgid in tree['groups']:
  before=time.monotonic_ns()
  try:os.killpg(pgid,signal.SIGKILL);error=None
  except ProcessLookupError:error='group_already_exited'
  signals.append({'pgrp':pgid,'signal':int(signal.SIGKILL),'before_ns':before,'after_ns':time.monotonic_ns(),'error':error})
 emit('SIGKILL_DISPATCH_RESULT',signals=signals)
 # A zombie cannot execute; verify original identities and any surviving browser process.
 deadline=time.monotonic()+5;observations=[]
 while True:
  observations=[]
  for old in tree['processes']:
   now=process(old['pid']);same=now is not None and now['start_ticks']==old['start_ticks']
   observations.append({'pid':old['pid'],'old_start_ticks':old['start_ticks'],'current':now,'original_identity_exited':not same or now['state']=='Z'})
  live=[r for r in inventory().values() if r['exe']==exe and has_profile(r,profile) and r['state']!='Z']
  if all(r['original_identity_exited'] for r in observations) and not live:break
  if time.monotonic()>=deadline:raise RuntimeError('Selected browser tree did not exit')
  time.sleep(.02)
 emit('SIGKILL_EXIT_EVIDENCE',selected=observations,profile_browser_survivors=live,all_selected_exited=True)

def main():
 config=json.loads(sys.stdin.readline())
 if config.get('role')!='qualification' or config.get('fault') not in ['browser_sigkill','sysrq_reboot']:raise RuntimeError('Qualification-only authorized fault required')
 profile=config['profile'];exe=config['exe']
 if not profile.startswith('/var/lib/idbv2/') or exe!='/opt/idbv2/browsers/chromium-1243/chrome-linux-arm64/chrome':raise RuntimeError('Unexpected profile/executable')
 emit('FAULT_AGENT_READY',role='qualification',fault=config['fault'],profile=profile,exe=exe)
 for line in sys.stdin:
  req=json.loads(line)
  if req.get('command')=='probe-tree':emit('TREE_PROBE',tree=select_tree(inventory(),profile,exe));continue
  if req.get('command')!='dispatch':raise RuntimeError('Unknown fault command')
  emit('FAULT_REQUEST_ACCEPTED',request_id=req['request_id'],fault=config['fault'])
  if config['fault']=='browser_sigkill':dispatch_sigkill(profile,exe)
  else:
   # root's explicit trigger is the registered immediate reboot, not panic or sync.
   emit('SYSRQ_REBOOT_REQUEST',trigger='/proc/sysrq-trigger',value='b',sysrq_enabled=pathlib.Path('/proc/sys/kernel/sysrq').read_text().strip())
   with pathlib.Path('/proc/sysrq-trigger').open('w') as f:f.write('b');f.flush()
   raise RuntimeError('Immediate reboot unexpectedly returned')
  return
if __name__=='__main__':main()
