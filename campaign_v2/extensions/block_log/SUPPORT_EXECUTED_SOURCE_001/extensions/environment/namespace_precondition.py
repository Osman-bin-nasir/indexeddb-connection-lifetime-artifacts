"""Persist only fresh pre-target directory namespace; never sync a target after writing."""
import os,json,re,sys,time
from pathlib import Path

def main():
 c=json.loads(sys.stdin.read());profile=Path(c['profile'])
 if c.get('phase')!='strict_sentinel_complete_target_absent':raise RuntimeError('Pre-target namespace phase required')
 if not re.fullmatch(r'/var/lib/idbv2/[A-Za-z0-9_-]+/profile',str(profile)):raise RuntimeError('Unsafe dedicated profile path')
 if not (profile/'Default/IndexedDB').is_dir():raise RuntimeError('Precondition missing expected IndexedDB namespace')
 dirs=[]
 for parent,names,files in os.walk(profile,followlinks=False):
  names[:]=[n for n in names if not (Path(parent)/n).is_symlink()];dirs.append(Path(parent))
 dirs.sort(key=lambda p:len(p.parts),reverse=True)
 ancestor=profile.parent
 while str(ancestor).startswith('/var/lib/idbv2'):
  dirs.append(ancestor)
  if ancestor==Path('/var/lib/idbv2'):break
  ancestor=ancestor.parent
 rows=[]
 for p in dirs:
  before=time.monotonic_ns();fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
  try:
   identity=os.fstat(fd);os.fsync(fd)
   rows.append({'path':str(p),'inode':identity.st_ino,'device':identity.st_dev,'start_ns':before,'return_ns':time.monotonic_ns(),'directory_fsync_returned':True})
  finally:os.close(fd)
 print(json.dumps({'role':'pre_target_namespace_only','phase':c['phase'],'profile':str(profile),'directories':rows,'target_has_not_been_requested':True,'file_fsync_performed':False}),flush=True)
if __name__=='__main__':main()
