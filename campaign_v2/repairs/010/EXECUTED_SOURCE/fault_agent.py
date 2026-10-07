"""Host pipe dispatcher with exact send/receipt timing and raw fault evidence."""
import json,shlex,subprocess,threading,time
from pathlib import Path

class FaultAgent:
 def __init__(self,ssh,port,assignment,profile,events,out):
  self.events=events;self.values=[];self.condition=threading.Condition();self.next=0
  path=Path(__file__).with_name('guest_fault_agent.py');source=path.read_text()
  self.error=(out/'fault-agent.stderr').open('xb')
  self.proc=subprocess.Popen(ssh(port)+['sudo python3 -u -c '+shlex.quote(source)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.error)
  self.thread=threading.Thread(target=self.read,daemon=True);self.thread.start()
  self.send({'role':'qualification','fault':assignment['fault'],'profile':profile,'exe':'/opt/idbv2/browsers/chromium-1243/chrome-linux-arm64/chrome'})
  self.wait('FAULT_AGENT_READY',10)
 def read(self):
  for raw in self.proc.stdout:
   receipt=time.monotonic_ns()
   try:value=json.loads(raw)
   except json.JSONDecodeError:
    self.events('FAULT_AGENT_NON_JSON',raw=raw.decode(errors='replace'));continue
   record=self.events('FAULT_AGENT_RECORD',fault_agent=value,receipt_ns=receipt)
   with self.condition:self.values.append(record);self.condition.notify_all()
  with self.condition:self.condition.notify_all()
 def send(self,value):
  before=time.monotonic_ns();self.proc.stdin.write((json.dumps(value)+'\n').encode());self.proc.stdin.flush();after=time.monotonic_ns()
  self.events('FAULT_AGENT_COMMAND',command=value,send_before_ns=before,send_after_ns=after)
  return before,after
 def wait(self,kind,timeout):
  end=time.monotonic()+timeout
  with self.condition:
   while True:
    for x in self.values:
     if x['fault_agent']['kind']==kind:return x
    if self.proc.poll() is not None and not self.thread.is_alive():raise RuntimeError('Fault agent exited before '+kind)
    if time.monotonic()>=end:raise TimeoutError('Missing fault record '+kind)
    self.condition.wait(.05)
 def probe(self):
  self.send({'command':'probe-tree'});return self.wait('TREE_PROBE',10)
 def dispatch(self):
  self.next+=1;before,after=self.send({'command':'dispatch','request_id':self.next})
  return {'dispatch_ns':before,'pipe_written_ns':after,'transport':'preopened guest SSH stdin','actual_guest_dispatch_separately_recorded':True}
 def close(self):
  if self.proc.poll() is None:
   self.proc.stdin.close()
   try:self.proc.wait(timeout=3)
   except subprocess.TimeoutExpired:self.proc.terminate();self.proc.wait(timeout=5)
  self.thread.join(timeout=5);self.error.close()
