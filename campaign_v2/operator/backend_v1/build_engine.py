"""Generate reviewable operator copies; preserve all executed qualification sources.

Only role/provenance, reserved output directory and helper deployment adaptations
are permitted. The generated diff and source hashes document every adaptation.
This builder does not provision a VM or execute any assignment.
"""
import ast,difflib,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent;ENGINE=HERE/'engine'
FOLDERS=['repairs/004','repairs/007','repairs/009','repairs/010','repairs/011','repairs/012','repairs/013','extensions/environment','extensions/block_log']
CONTROLLERS={'qualification_candidate.py','qualification_workloads.py','qualification_fault_scope.py','qualification_timelines.py','qualification_bytes.py','qualification_mapped.py','qualification_environment.py','qualification_log.py'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def parse(s):return ast.parse(s)
def expr(s):return parse(s).body[0].value
class Adapt(ast.NodeTransformer):
 def __init__(self,path):self.path=path;self.controller=path.name in CONTROLLERS;self.audit=path.name=='independent_audit.py';self.guest=path.name.startswith('guest_');self.host=not self.guest;self.changes=[]
 def change(self,kind,node):self.changes.append({'kind':kind,'line':getattr(node,'lineno',None)})
 def visit_Assign(self,n):
  n=self.generic_visit(n)
  if self.host and any(isinstance(t,ast.Name) and t.id=='ROOT' for t in n.targets):
   n.value=expr(f'Path(__file__).resolve().parents[{len(self.path.relative_to(ROOT).parts)+2}]');self.change('host campaign root for copied path',n)
  if self.path.name=='guest_worker.py' and any(isinstance(t,ast.Name) and t.id=='ROOT' for t in n.targets):n.value=expr("Path('/opt/idbv2/worker')");self.change('original transaction.js directory retained',n)
  if self.host and self.controller and any(isinstance(t,ast.Name) and t.id=='BASE' for t in n.targets):n.value=expr("ROOT/'repairs/003/mount-pinned-base.qcow2'");self.change('unchanged qualified base at original path',n)
  if self.host and any(isinstance(t,ast.Name) and t.id=='ATTEMPTS' for t in n.targets):n.value=expr('attempt_root()');self.change('role-specific attempt root',n)
  return n
 def visit_BinOp(self,n):
  # Redirect engineering module/helper lookups to the explicit new copies.
  def path(x):
   if isinstance(x,ast.Name) and x.id=='ROOT':return ''
   if isinstance(x,ast.BinOp) and isinstance(x.op,ast.Div) and isinstance(x.right,ast.Constant) and isinstance(x.right.value,str):
    l=path(x.left)
    if l is not None:return (l+'/'+x.right.value).strip('/')
  p=path(n)
  if self.host and p and any(p==f or p.startswith(f+'/') for f in FOLDERS):self.change('operator helper source directory',n);return ast.copy_location(expr('ENGINE/'+repr(p)),n)
  return self.generic_visit(n)
 def visit_Constant(self,n):
  if self.host and n.value=='qualification' and (self.controller or self.path.name=='fault_agent.py'):self.change('explicit assignment role',n);return ast.copy_location(ast.Name(id='RUN_ROLE',ctx=ast.Load()),n)
  if self.host and self.audit and n.value=='qualification':self.change('audit assignment role',n);return ast.copy_location(ast.Name(id='RUN_ROLE',ctx=ast.Load()),n)
  if self.host and self.audit and n.value=='qualification/attempts':return ast.copy_location(ast.Name(id='ATTEMPT_RELATIVE',ctx=ast.Load()),n)
  if self.host and (self.controller or self.audit) and n.value=='START.json':self.change('engine start separated from operator reservation',n);return ast.copy_location(ast.Constant(value='ENGINE_START.json'),n)
  if self.host and (self.controller or self.audit) and n.value=='qualification_passed':self.change('technical eligibility output name',n);return ast.copy_location(ast.Constant(value='technical_eligible'),n)
  if self.host and isinstance(n.value,str) and 'xvfb-run' in n.value and '/opt/idbv2/worker/guest_worker.py' in n.value:
   self.change('role-capable worker launch',n);return ast.copy_location(ast.Constant(value=n.value.replace('/opt/idbv2/worker/guest_worker.py','/opt/idbv2/operator/guest_worker.py')),n)
  if self.host and self.controller and n.value=='/opt/idbv2/worker/guest_worker.py':
   self.change('role-capable worker path',n);return ast.copy_location(ast.Constant(value='/opt/idbv2/operator/guest_worker.py'),n)
  return n
 def visit_Compare(self,n):
  # Guest helpers accept the explicit role. Browser measurement logic unchanged.
  if self.guest and len(n.ops)==1 and isinstance(n.ops[0],ast.NotEq) and len(n.comparators)==1 and isinstance(n.comparators[0],ast.Constant) and n.comparators[0].value=='qualification':
   self.change('guest allows registered scientific or excluded role',n);n.ops=[ast.NotIn()];n.comparators=[expr("('qualification','scientific')")]
  if self.guest and len(n.ops)==1 and isinstance(n.ops[0],ast.NotIn) and len(n.comparators)==1 and isinstance(n.comparators[0],(ast.List,ast.Tuple)) and any(isinstance(v,ast.Constant) and v.value=='qualification' for v in n.comparators[0].elts):
   n.comparators[0].elts.append(ast.Constant(value='scientific'));self.change('guest isolated setup explicit scientific role',n)
  n=self.generic_visit(n)
  if self.audit and len(n.ops)==1 and isinstance(n.ops[0],ast.Eq) and isinstance(n.left,ast.Subscript) and isinstance(n.left.slice,ast.Constant) and n.left.slice.value=='scientific_assignments_started':n.comparators=[expr("int(RUN_ROLE=='scientific')")];self.change('audit actual current role count',n)
  # Provenance checks in independent audits require the actual denominator.
  if self.audit and len(n.ops)==1 and isinstance(n.ops[0],ast.Is) and len(n.comparators)==1 and isinstance(n.comparators[0],ast.Constant) and n.comparators[0].value is False and isinstance(n.left,ast.Subscript) and isinstance(n.left.slice,ast.Constant) and n.left.slice.value=='scientific_denominator':n.comparators=[expr("RUN_ROLE=='scientific'")];n.ops=[ast.Eq()];self.change('audit explicit denominator',n)
  return n
 def visit_Dict(self,n):
  n=self.generic_visit(n)
  if self.host and (self.controller or self.audit):
   for i,k in enumerate(n.keys):
    if isinstance(k,ast.Constant) and k.value=='scientific_denominator':n.values[i]=expr("RUN_ROLE=='scientific'");self.change('explicit scientific denominator',n)
    if isinstance(k,ast.Constant) and k.value=='scientific_assignments_started':n.values[i]=expr("int(RUN_ROLE=='scientific')");self.change('actual current attempt role count',n)
  return n
 def visit_Expr(self,n):
  if self.controller and isinstance(n.value,ast.Call):
   c=n.value
   if isinstance(c.func,ast.Attribute) and isinstance(c.func.value,ast.Name) and c.func.value.id=='out' and c.func.attr=='mkdir':self.change('validate pre-reserved attempt instead of recreating',n);return ast.copy_location(parse('validate_reserved(out, assignment if "assignment" in locals() else a)').body[0],n)
   if isinstance(c.func,ast.Name) and c.func.id=='save' and c.args and isinstance(c.args[0],ast.BinOp) and isinstance(c.args[0].left,ast.Name) and c.args[0].left.id=='out' and isinstance(c.args[0].right,ast.Constant) and c.args[0].right.value=='assignment.json':self.change('verify immutable operator assignment',n);return ast.copy_location(parse('validate_assignment(out, assignment if "assignment" in locals() else a)').body[0],n)
  return self.generic_visit(n)
 def visit_FunctionDef(self,n):
  n=self.generic_visit(n)
  if self.host and self.controller and n.name=='__init__' and any(a.arg=='spec' for a in n.args.args) and any(a.arg=='vm' for a in n.args.args):
   n.body.insert(0,parse('deploy_worker(remote, vm.port, events)').body[0]);self.change('verify additional worker before any target operation',n)
  return n
 def visit_Call(self,n):
  n=self.generic_visit(n)
  if self.guest and self.path.name=='guest_fault_agent.py':
   for k in n.keywords:
    if k.arg=='role' and isinstance(k.value,ast.Constant) and k.value.value=='qualification':k.value=expr("config['role']");self.change('fault agent reports actual role',n)
  if self.controller and isinstance(n.func,ast.Name) and n.func.id=='sha' and n.args and ast.unparse(n.args[0])=="ROOT / 'guest_worker.py'":
   # Recovery/byte worker path now has a separate prospective source hash. Base
   # lock FILES still checks the original worker and original base unchanged.
   # This expression occurs only in the reader-specific executable check.
   n.args[0]=expr("ENGINE/'guest_worker.py'");self.change('additional worker executable hash',n)
  return n
 def visit_comprehension(self,n):
  n=self.generic_visit(n)
  if self.controller and isinstance(n.target,ast.Name) and n.target.id=='p' and any(isinstance(i,ast.Call) and isinstance(i.func,ast.Attribute) and i.func.attr=='is_file' for i in n.ifs):n.ifs.append(expr("p.name != 'backend-console.txt'"));self.change('console sealed by operator after backend exits',n)
  return n

def main():
 if (HERE/'INTEGRATION_PLAN_001.json').exists():raise RuntimeError('Prospectively locked engine cannot be regenerated')
 ENGINE.mkdir(exist_ok=True);records=[];diff=[]
 files=[ROOT/'guest_worker.py']
 for f in FOLDERS:files+=sorted((ROOT/f).glob('*.py'))
 for p in files:
  rel=p.relative_to(ROOT);dst=ENGINE/rel;dst.parent.mkdir(parents=True,exist_ok=True);original=p.read_text();adapter=Adapt(p);tree=adapter.visit(parse(original))
  if adapter.host:
   imports=parse('from backend_runtime import RUN_ROLE, ENGINE, ATTEMPT_RELATIVE, attempt_root, validate_reserved, validate_assignment, deploy_worker').body
   at=1 if tree.body and isinstance(tree.body[0],ast.Expr) and isinstance(tree.body[0].value,ast.Constant) and isinstance(tree.body[0].value.value,str) else 0
   while at<len(tree.body) and isinstance(tree.body[at],ast.ImportFrom) and tree.body[at].module=='__future__':at+=1
   tree.body[at:at]=imports
  adapted=ast.unparse(ast.fix_missing_locations(tree))+'\n';compile(adapted,str(dst),'exec');dst.write_text(adapted)
  records.append({'original':str(rel),'original_sha256':sha(p),'generated':str(dst.relative_to(ROOT)),'generated_sha256':sha(dst),'adaptations':adapter.changes})
  diff+=list(difflib.unified_diff(original.splitlines(True),adapted.splitlines(True),fromfile=str(rel),tofile=str(dst.relative_to(ROOT))))
 for f in FOLDERS:
  folder=ENGINE/f
  for p in (ROOT/f).glob('*.bt'):shutil.copy2(p,folder/p.name)
  shutil.copy2(ROOT/f/'REPAIRED_BASE_LOCK.json',folder/'REPAIRED_BASE_LOCK.json')
  snap=folder/'EXECUTED_SOURCE';snap.mkdir(exist_ok=True)
  for p in folder.glob('*.py'):shutil.copy2(p,snap/p.name)
 (HERE/'ENGINE_ADAPTATION.diff').write_text(''.join(diff))
 (HERE/'ENGINE_SOURCE_MANIFEST.json').write_text(json.dumps({'stage':'unqualified_operator_integration','scientific_started':0,'frozen_scientific_design_unchanged':True,'files':records},indent=2)+'\n')
 print('Generated',len(records),'reviewable source copies; no assignments executed')
if __name__=='__main__':main()
