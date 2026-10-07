"""Join observed syscall bytes to kernel file identities conservatively by TID and ordered FD/operation/return evidence."""
import copy,hashlib
from strace_decode import decode,WRITE

def kernel_records(raw):
 records=[];returned={};issues=[]
 for line in raw.splitlines():
  if line.startswith('FILE '):
   p=line.split()
   if len(p)!=13:issues.append({'issue':'invalid_FILE_record','text':line});continue
   v=list(map(int,p[1:12]));records.append(dict(zip(['kernel_ns','tgid','tid','fd','call_id','file_pointer','generation_ns','kernel_dev_t','inode','offset','requested_bytes'],v),kind=p[12]))
  elif line.startswith('RETURN '):
   _,stamp,tid,call,value=line.split();key=(int(tid),int(call))
   if key in returned:issues.append({'issue':'duplicate_return','tid':int(tid),'call':int(call)})
   returned[key]={'return':int(value),'return_ns':int(stamp)}
 for r in records:
  ret=returned.get((r['tid'],r['call_id']));r.update(ret or {'return':None,'return_ns':None})
 return records,issues

def join(strace_raw,kernel_raw,profile):
 decoded=decode(strace_raw,'/');kernel,issues=kernel_records(kernel_raw);groups={}
 for r in kernel:groups.setdefault(r['tid'],[]).append(r)
 used=set();last={};out=[];failed=[]
 # Sequence alignment across every observed absolute-path operation on the root device.
 # A duplicate/ambiguous matching kernel record is never an invented identity.
 for row in sorted(decoded['records'],key=lambda r:r['line']):
  kind='sync' if row['syscall'] not in WRITE else 'write' if row['syscall'] in ['write','pwrite64'] else 'vector'
  options=[(i,k) for i,k in enumerate(groups.get(row['pid'],[])) if i>=last.get(row['pid'],0) and k['fd']==row['fd'] and k['kind']==kind and k['return']==row['returned'] and (kind=='sync' or k['requested_bytes']==row['requested_bytes'])]
  # Only the earliest matching observation is used; preserve identities and kernel call IDs.
  selected=options[0] if options else None
  relevant=profile in (row['path'] or '')
  if selected:
   i,k=selected;last[row['pid']]=i+1;used.add((k['tid'],k['call_id']));r=copy.deepcopy(row)
   r.update(strace_ofd=row['ofd'],strace_offset=row['offset'],kernel_identity=k,ofd=f"kernel-file-{k['file_pointer']}-{k['generation_ns']}",ofd_basis='observed kernel struct file pointer with security_file_open or first-observation generation; __fput invalidates reuse',device={'major':k['kernel_dev_t']>>20,'minor':k['kernel_dev_t']&((1<<20)-1)},inode=k['inode'],offset=k['offset'] if kind!='sync' else None,identity_observed_before_call=True)
   if relevant:out.append(r)
  elif relevant:
   failed.append({'line':row['line'],'pid':row['pid'],'fd':row['fd'],'syscall':row['syscall'],'returned':row['returned'],'path':row['path'],'issue':'No matching observed kernel file identity/return'});out.append(row)
 writes=[r for r in out if r['syscall'] in WRITE]
 return {'raw_strace_sha256':hashlib.sha256(strace_raw.encode()).hexdigest(),'raw_kernel_sha256':hashlib.sha256(kernel_raw.encode()).hexdigest(),'records':out,'unresolved_matches':failed,'kernel_diagnostics':issues,'unfinished_strace_calls':decoded['unfinished_calls'],'strace_diagnostics':decoded['diagnostics'],'all_profile_write_bytes_complete':bool(writes) and all(r['full_argument_bytes'] for r in writes),'all_profile_write_identity_complete':bool(writes) and all('kernel_identity' in r for r in writes),'all_profile_write_offsets_complete':bool(writes) and all(r['offset'] is not None for r in writes),'no_unmatched_profile_calls':not any(profile in v['text'] for v in decoded['unfinished_calls']),'absence_of_unobserved_events_established':False,'callback_attribution':'not established','stream_boundary_loss_requires_separate_receipt':True,'pairing_method':'ordered per-TID FD, VFS-operation, byte count and observed return alignment across all absolute-path calls; preserve raw source line and kernel call IDs'}
