"""Neutral file IO witness. No browser, database, assigned fault or target transaction."""
import hashlib,json,os,pathlib
p=pathlib.Path('/tmp/idbv2-neutral-byte-capture');p.mkdir(exist_ok=False)
fd=os.open(p/'first.bin',os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600)
s=os.fstat(fd);ofd='first-open-epoch'
witness=[]
def note(kind,**v):witness.append(dict(kind=kind,pid=os.getpid(),**v))
def output(data):return dict(bytes=len(data),hex=data.hex(),sha256=hashlib.sha256(data).hexdigest())
a=bytes(range(256))*16
note('identity',fd=fd,device=s.st_dev,inode=s.st_ino,ofd=ofd)
note('write',fd=fd,offset=0,result=os.write(fd,a),**output(a))
b=b'neutral-pwrite-marker\x00\xff';note('pwrite64',fd=fd,offset=8192,result=os.pwrite(fd,b,8192),**output(b))
dup=os.dup(fd);note('dup',old=fd,new=dup,ofd=ofd);os.fstat(dup)
os.lseek(dup,12288,os.SEEK_SET)
c=[b'neutral-vector-one',b'\x00\xfevector-two'];note('writev',fd=dup,offset=12288,result=os.writev(dup,c),**output(b''.join(c)))
d=[b'positioned-one',b'\x01positioned-two'];note('pwritev',fd=fd,offset=16384,result=os.pwritev(fd,d,16384),**output(b''.join(d)))
pid=os.fork()
if pid==0:
 os.fstat(fd);os.pwrite(fd,b'child-pwrite',20480);os.fdatasync(fd);os.close(fd);os.close(dup);os._exit(0)
os.waitpid(pid,0);note('child',pid_child=pid,fd=fd,offset=20480,result=12,ofd=ofd,**output(b'child-pwrite'))
os.fsync(fd);note('fsync',fd=fd,result=0,ofd=ofd);os.close(dup);os.close(fd)
fd2=os.open(p/'second.bin',os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600);s2=os.fstat(fd2)
e=b'reused-descriptor-different-file';note('identity',fd=fd2,device=s2.st_dev,inode=s2.st_ino,ofd='second-open-epoch')
note('write',fd=fd2,offset=0,result=os.write(fd2,e),**output(e));os.fsync(fd2);os.close(fd2)
print(json.dumps({'role':'support_only','witness':witness,'files':[{ 'name':x.name,'bytes':x.stat().st_size,'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in sorted(p.iterdir())]}))
