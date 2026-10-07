"""Conservative strace6.8 decoder. Unresolved identity, offsets and unfinished calls stay explicit."""
import hashlib,json,re
from pathlib import Path
WRITE={'write','pwrite64','writev','pwritev','pwritev2'}
SYNC={'fsync','fdatasync','sync','syncfs'}
HEADER=re.compile(r'^(\d+)\s+(\d+\.\d+)\s+(.*)$')
HEXSTRING=re.compile(r'"((?:\\x[0-9a-fA-F]{2})*)"')
def decoded(s):
 return bytes.fromhex(s.replace('\\x',''))
def path_of(s):
 m=re.search(r'<((?:\\x[0-9a-fA-F]{2})+)>',s)
 return decoded(m[1]).decode('utf-8',errors='surrogateescape') if m else None
def fdnum(s):
 m=re.match(r'-?\d+',s);return int(m[0]) if m else None
def split_args(s):
 vals=[];start=0;depth=0;quote=False;escape=False
 for n,c in enumerate(s):
  if quote:
   if escape:escape=False
   elif c=='\\':escape=True
   elif c=='"':quote=False
  elif c=='"':quote=True
  elif c in '[{(':depth+=1
  elif c in ']})':depth-=1
  elif c==',' and depth==0:vals.append(s[start:n].strip());start=n+1
 vals.append(s[start:].strip());return vals

def decode(raw,profile):
 tables={};ofds={};pending={};issues=[];rows=[];calls=[];serial=0
 def table(pid):return tables.setdefault(pid,{})
 for number,line in enumerate(raw.splitlines(),1):
  m=HEADER.match(line)
  if not m:
   if line.startswith('strace:'):issues.append({'line':number,'issue':'strace_diagnostic','text':line})
   continue
  pid=int(m[1]);stamp=m[2];body=m[3];origin=number
  if '<unfinished ...>' in body:
   if pid in pending:issues.append({'line':number,'issue':'multiple_pending_calls','pid':pid})
   pending[pid]=(body.split('<unfinished ...>')[0],number,stamp);continue
  resumed=re.match(r'<\.\.\. (\w+) resumed>(.*)',body)
  if resumed:
   if pid not in pending:issues.append({'line':number,'issue':'unmatched_resume','pid':pid});continue
   prefix,origin,stamp=pending.pop(pid);body=prefix+resumed[2]
  call=re.match(r'(\w+)\((.*)\)\s+=\s+(-?\d+)(.*)',body)
  if not call:continue
  name=call[1];args=split_args(call[2]);returned=int(call[3]);fd=fdnum(args[0]) if args else None
  t=table(pid);ofd=t.get(fd);obj=ofds.get(ofd);fdpath=path_of(args[0]) if args else None
  calls.append({'line':origin,'return_line':number,'pid':pid,'name':name,'return':returned})
  if name in ['open','openat','openat2'] and returned>=0:
   serial+=1;ofd=f'open-{pid}-{serial}';p=re.findall(HEXSTRING,args[1] if name!='open' else args[0]);path=decoded(p[0]).decode('utf-8',errors='surrogateescape') if p else path_of(str(returned)+call[4])
   flags=','.join(args[2:] if name!='open' else args[1:]);ofds[ofd]={'path':path,'device':None,'inode':None,'offset':0,'open_line':origin,'append':'O_APPEND' in flags,'identity_line':None};t[returned]=ofd
  elif name in ['dup','dup2','dup3'] or name=='fcntl' and len(args)>1 and args[1] in ['F_DUPFD','F_DUPFD_CLOEXEC']:
   if returned>=0:t[returned]=ofd
  elif name in ['clone','clone3','fork','vfork'] and returned>0:
   tables[returned]=t if 'CLONE_FILES' in call[2] else dict(t)
  elif name in ['fstat','newfstatat'] and returned==0 and obj:
   # Only fstat or AT_EMPTY_PATH proves identity for this opened description.
   if name=='fstat' or 'AT_EMPTY_PATH' in call[2]:
    ino=re.search(r'st_ino=(\d+)',call[2]);dev=re.search(r'st_dev=makedev\((0x[0-9a-f]+|\d+), (0x[0-9a-f]+|\d+)\)',call[2])
    if ino and dev:obj.update(inode=int(ino[1]),device={'major':int(dev[1],0),'minor':int(dev[2],0)},identity_line=origin)
  elif name=='lseek' and returned>=0 and obj:obj['offset']=returned
  elif name in WRITE|SYNC:
   relevant=(obj and obj.get('path') and profile in obj['path']) or (fdpath and profile in fdpath)
   if name in ['sync','syncfs']:relevant=True
   if relevant:
    strings=[];data=b'';requested=None;offset=None;complete=None
    if name in WRITE:
     strings=HEXSTRING.findall(args[1]);data=b''.join(decoded(x) for x in strings)
     if name in ['write','pwrite64']:
      requested=int(args[2]);offset=int(args[3]) if name=='pwrite64' else (obj['offset'] if obj and not obj['append'] else None)
     else:
      lengths=re.findall(r'iov_len=(\d+)',args[1]);requested=sum(map(int,lengths));offset=int(args[3]) if name in ['pwritev','pwritev2'] else (obj['offset'] if obj and not obj['append'] else None)
     complete=len(data)==requested and not re.search(r'"\.\.\.|\}, \.\.\.',args[1])
    identity_complete=bool(obj and obj['device'] is not None and obj['inode'] is not None and obj['identity_line']<origin)
    r={'line':origin,'return_line':number,'pid':pid,'guest_realtime_seconds':stamp,'syscall':name,'fd':fd,'path':obj['path'] if obj else fdpath,'ofd':ofd,'ofd_basis':'observed open; dup/fork inheritance and CLONE_FILES sharing' if ofd else 'unresolved','device':obj['device'] if obj else None,'inode':obj['inode'] if obj else None,'identity_observed_before_call':identity_complete,'offset':offset,'requested_bytes':requested,'returned':returned,'data_hex':data.hex() if name in WRITE else None,'data_sha256':hashlib.sha256(data).hexdigest() if name in WRITE else None,'full_argument_bytes':complete,'return_observed':True}
    rows.append(r)
    if name in WRITE and returned>0 and name in ['write','writev'] and obj:obj['offset']=offset+returned if offset is not None else None
  if name=='close' and returned==0:t.pop(fd,None)
  if name=='close_range' and returned==0:
   if 'CLOSE_RANGE_UNSHARE' in call[2]:tables[pid]=dict(t);t=tables[pid]
   if 'CLOSE_RANGE_CLOEXEC' not in call[2]:
    lo=int(args[0]);hi=2**32-1 if args[1]=='~0U' else int(args[1]);
    for x in list(t):
     if lo<=x<=hi:t.pop(x)
 # Finished strace can still have a syscall interrupted by an externally registered fault.
 unmatched=[{'pid':p,'line':v[1],'text':v[0],'timestamp':v[2]} for p,v in pending.items()]
 writes=[r for r in rows if r['syscall'] in WRITE]
 return {'raw_sha256':hashlib.sha256(raw.encode()).hexdigest(),'records':rows,'open_descriptions':ofds,'diagnostics':issues,'unfinished_calls':unmatched,'all_profile_write_bytes_complete':bool(writes) and all(r['full_argument_bytes'] for r in writes),'all_profile_write_identity_complete':bool(writes) and all(r['identity_observed_before_call'] and r['ofd'] for r in writes),'all_profile_write_offsets_complete':bool(writes) and all(r['offset'] is not None for r in writes),'no_unmatched_profile_calls':not any(profile in (path_of(v['text']) or '') for v in unmatched),'absence_of_unobserved_events_established':False,'callback_attribution':'not established'}
