"""Preserve an immutable external disk snapshot while retaining the original guest."""
from pathlib import Path
import time
from provision_vm import sha,save

def capture(vm,disk,out,events):
 target=out/'active-after-snapshot.qcow2'
 if target.exists():raise RuntimeError('Refusing to overwrite active snapshot')
 stopped=vm.qmp.execute('stop');status=vm.qmp.execute('query-status')
 if status['return']['status']!='paused':raise RuntimeError('Guest is not paused at capture')
 blocks=vm.qmp.execute('query-block')['return']
 matches=[b for b in blocks if b.get('inserted',{}).get('file')==str(disk)]
 if len(matches)!=1 or not matches[0].get('device'):raise RuntimeError('Original writable root disk identity is not unique')
 original=matches[0];node=original['inserted']['node-name']
 snapshot=vm.qmp.execute('blockdev-snapshot-sync',{'device':original['device'],'snapshot-file':str(target),'format':'qcow2','mode':'absolute-paths'})
 changed=vm.qmp.execute('query-block')['return'];active=[b for b in changed if b.get('device')==original['device']]
 if len(active)!=1 or active[0]['inserted']['file']!=str(target):raise RuntimeError('Active root was not redirected to separate overlay')
 nodes=vm.qmp.execute('query-named-block-nodes')['return'];old=[n for n in nodes if n.get('node-name')==node]
 if len(old)!=1 or old[0].get('ro') is not True:raise RuntimeError('Captured source node is not read-only')
 disk.chmod(0o444);digest=sha(disk)
 value={'source':str(disk),'sha256':digest,'captured_ns':time.monotonic_ns(),'active_after_snapshot':str(target),'original_qemu_pid':vm.proc.pid,'original_boot_id':vm.boot,'guest_shutdown_before_oracle':False,'guest_volatile_state_retained':True,'disk_node_read_only':True,'pause':stopped,'snapshot':snapshot,'query_block_after':changed,'source_node_after':old[0],'instantaneous_crash_state':False,'oracle_started':False}
 save(out/'LIVE_SNAPSHOT.json',value);events('LIVE_SNAPSHOT_RETAINS_ORIGINAL_GUEST',capture=value)
 return value
