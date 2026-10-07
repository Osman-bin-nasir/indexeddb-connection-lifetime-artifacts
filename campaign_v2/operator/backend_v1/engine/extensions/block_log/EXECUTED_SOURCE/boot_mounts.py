"""Pin auxiliary mount selectors to verified devices in the fixed VM topology."""
from backend_runtime import RUN_ROLE, ENGINE, ATTEMPT_RELATIVE, attempt_root, validate_reserved, validate_assignment, deploy_worker
EXPECTED = {'/boot': {'device': '/dev/vda16', 'label': 'BOOT', 'type': 'ext4', 'uuid': '5b886046-3262-4eca-a390-4cd88779a3c7', 'partuuid': 'c81133b1-6578-4173-8ee3-2d635e1cf0f4'}, '/boot/efi': {'device': '/dev/vda15', 'label': 'UEFI', 'type': 'vfat', 'uuid': '1C9E-FED1', 'partuuid': '8242a1d8-b6a4-44a4-971d-634818e90362'}}

def transform(text):
    lines = text.splitlines(keepends=True)
    seen = set()
    output = []
    for line in lines:
        fields = line.split()
        if not fields or fields[0].startswith('#'):
            output.append(line)
            continue
        if len(fields) != 6:
            raise ValueError('Unexpected fstab entry')
        mount = fields[1]
        if mount in EXPECTED:
            if mount in seen:
                raise ValueError('Duplicate auxiliary mount')
            expected = EXPECTED[mount]
            suffix = {'/boot': ['ext4', 'defaults', '0', '2'], '/boot/efi': ['vfat', 'umask=0077', '0', '1']}[mount]
            if fields[0] != 'LABEL=' + expected['label'] or fields[2:] != suffix:
                raise ValueError('Unexpected auxiliary mount specification')
            seen.add(mount)
            start = line.index(fields[0])
            line = line[:start] + expected['device'] + line[start + len(fields[0]):]
        output.append(line)
    if seen != set(EXPECTED):
        raise ValueError('Missing auxiliary mount')
    return ''.join(output)

def validate_inventory(inventory):
    if inventory['root_source'] != '/dev/vda1':
        raise ValueError('Wrong root device')
    for mount, e in EXPECTED.items():
        if inventory['partitions'].get(e['device']) != {k: e[k] for k in ['label', 'type', 'uuid', 'partuuid']}:
            raise ValueError('Partition identity mismatch: ' + mount)
        if inventory['mount_sources'].get(mount) != e['device']:
            raise ValueError('Auxiliary mount source mismatch: ' + mount)
INVENTORY_COMMAND = "python3 - <<'PYREMOTE'\nimport json,subprocess,pathlib\nrun=lambda args:subprocess.check_output(args,text=True).strip()\npartitions={}\ntable=json.loads(run(['sudo','sfdisk','--json','/dev/vda']))['partitiontable']\nif table['label']!='gpt':raise RuntimeError('Unexpected partition table')\nentries={p['node']:p['uuid'].lower() for p in table['partitions']}\nfor dev in ['/dev/vda16','/dev/vda15']:\n values=dict(line.split('=',1) for line in run(['sudo','blkid','-p','-o','export',dev]).splitlines() if '=' in line)\n partitions[dev]={'label':values.get('LABEL'),'type':values.get('TYPE'),'uuid':values.get('UUID'),'partuuid':entries[dev]}\nprint(json.dumps({'root_source':run(['findmnt','-nr','-o','SOURCE','/']),'partitions':partitions,'mount_sources':{m:run(['findmnt','-nr','-o','SOURCE',m]) for m in ['/boot','/boot/efi']},'fstab':pathlib.Path('/etc/fstab').read_text()}))\nPYREMOTE"

def checked_inventory(remote, port, out, stage, expected_fstab=None):
    import json
    r = remote(port, INVENTORY_COMMAND, check=False)
    (out / (stage + '.stdout')).write_bytes(r.stdout)
    (out / (stage + '.stderr')).write_bytes(r.stderr)
    (out / (stage + '.returncode.json')).write_text(json.dumps({'returncode': r.returncode}) + '\n')
    if r.returncode:
        raise ValueError('Mount inventory command failed')
    value = json.loads(r.stdout)
    validate_inventory(value)
    if expected_fstab is not None and value['fstab'] != expected_fstab:
        raise ValueError('fstab bytes changed')
    return value
