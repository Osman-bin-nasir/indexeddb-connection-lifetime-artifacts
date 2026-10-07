"""Read small source files from preserved guest disks, without boot or replay.

qemu-img dd performs read-only virtual reads, including qcow2 backing/compressed
clusters. This bounded ext4 reader walks extents and directory entries only.
Original images are inputs; extracts and the report go to this new directory.
This is an investigation utility, never a scientific controller or validator.
"""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[2]
ATTEMPT = CAMPAIGN / 'scientific/attempts/scientific-target_byte_diagnostics-00001'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class Disk:
    def __init__(self, image, scratch):
        self.image, self.scratch, self.cache = image, scratch, {}

    def read(self, offset, count):
        pieces = []
        while count:
            cluster, within = divmod(offset, 65536)
            if cluster not in self.cache:
                target = self.scratch / 'virtual-block.bin'
                subprocess.run(['qemu-img', 'dd', '-f', 'qcow2',
                                'if=' + str(self.image), 'of=' + str(target),
                                'bs=65536', 'skip=' + str(cluster),
                                'count=' + str(cluster + 1)],
                               check=True, capture_output=True)
                value = target.read_bytes()
                if len(value) != 65536:
                    raise RuntimeError('Short virtual block read')
                self.cache[cluster] = value
            n = min(count, 65536 - within)
            pieces.append(self.cache[cluster][within:within + n])
            offset, count = offset + n, count - n
        return b''.join(pieces)


class Ext4:
    def __init__(self, disk):
        self.disk = disk
        gpt = disk.read(512, 512)
        if gpt[:8] != b'EFI PART':
            raise RuntimeError('GPT header required')
        table_lba = struct.unpack_from('<Q', gpt, 72)[0]
        entry_size = struct.unpack_from('<I', gpt, 84)[0]
        # The locked Ubuntu image records its root filesystem on partition 1.
        entry = disk.read(table_lba * 512, entry_size)
        first, last = struct.unpack_from('<QQ', entry, 32)
        self.offset = first * 512
        self.partition = {'number': 1, 'first_lba': first, 'last_lba': last}
        sb = disk.read(self.offset + 1024, 1024)
        if struct.unpack_from('<H', sb, 56)[0] != 0xef53:
            raise RuntimeError('Root partition is not ext4')
        self.block_size = 1024 << struct.unpack_from('<I', sb, 24)[0]
        self.inodes_per_group = struct.unpack_from('<I', sb, 40)[0]
        self.inode_size = struct.unpack_from('<H', sb, 88)[0]
        self.desc_size = max(32, struct.unpack_from('<H', sb, 254)[0])
        self.gdt_offset = (2 if self.block_size == 1024 else 1) * self.block_size

    def block(self, number):
        return self.disk.read(self.offset + number * self.block_size, self.block_size)

    def inode(self, number):
        group, index = divmod(number - 1, self.inodes_per_group)
        desc = self.disk.read(self.offset + self.gdt_offset + group * self.desc_size,
                              self.desc_size)
        table = struct.unpack_from('<I', desc, 8)[0]
        if self.desc_size >= 64:
            table |= struct.unpack_from('<I', desc, 40)[0] << 32
        return self.disk.read(self.offset + table * self.block_size + index * self.inode_size,
                              self.inode_size)

    def extents(self, tree):
        magic, entries, maximum, depth = struct.unpack_from('<HHHH', tree)
        if magic != 0xf30a or entries > maximum or depth > 5:
            raise RuntimeError('Unsupported or invalid extent tree')
        output = []
        for i in range(entries):
            at = 12 + 12 * i
            if depth:
                _, low, high = struct.unpack_from('<IIH', tree, at)
                output.extend(self.extents(self.block(low | high << 32)))
            else:
                logical, length, high, low = struct.unpack_from('<IHHI', tree, at)
                uninitialized = length > 32768
                actual_length = length - 32768 if uninitialized else length
                output.append((logical, actual_length, low | high << 32, uninitialized))
        return output

    def content(self, inode, limit=2 * 1024 * 1024):
        mode = struct.unpack_from('<H', inode)[0]
        size = struct.unpack_from('<I', inode, 4)[0] | struct.unpack_from('<I', inode, 108)[0] << 32
        if size > limit:
            raise RuntimeError('Bounded source/directory extraction limit exceeded')
        if mode & 0xf000 == 0xa000 and size <= 60:
            return inode[40:40 + size]
        if not struct.unpack_from('<I', inode, 32)[0] & 0x80000:
            raise RuntimeError('Only extents supported')
        output = bytearray(size)
        for logical, count, physical, uninitialized in self.extents(inode[40:100]):
            if uninitialized:
                continue
            for i in range(count):
                pos = (logical + i) * self.block_size
                if pos >= size:
                    break
                data = self.block(physical + i)[:min(self.block_size, size - pos)]
                output[pos:pos + len(data)] = data
        return bytes(output)

    def lookup(self, guest_path):
        current = 2
        for component in Path(guest_path).parts[1:]:
            data = self.content(self.inode(current))
            found = None
            for block_start in range(0, len(data), self.block_size):
                pos, end = block_start, min(block_start + self.block_size, len(data))
                while pos + 8 <= end:
                    number, length, namelen = struct.unpack_from('<IHB', data, pos)
                    if length < 8 or pos + length > end:
                        raise RuntimeError('Invalid directory entry')
                    name = data[pos + 8:pos + 8 + namelen].decode('utf-8', errors='strict')
                    if number and name == component:
                        found = number
                    pos += length
            if found is None:
                raise FileNotFoundError(guest_path)
            current = found
        return current, self.content(self.inode(current))


def main():
    report = {'method': 'read-only qemu-img virtual block reads and bounded ext4 extent walk',
              'vm_booted': False, 'journal_replayed': False, 'images': []}
    paths = ['/opt/idbv2/operator/guest_worker.py', '/opt/idbv2/worker/guest_worker.py',
             '/opt/idbv2/worker/transaction.js']
    for name in ['overlay.qcow2', 'recovery.qcow2']:
        image = ATTEMPT / name
        before = sha(image)
        row = {'image': name, 'sha256_before': before, 'files': []}
        with tempfile.TemporaryDirectory(prefix='idbv2-readonly-source-inspection-') as scratch:
            disk = Disk(image, Path(scratch))
            filesystem = Ext4(disk)
            row['root_partition'] = filesystem.partition
            row['block_size'] = filesystem.block_size
            for guest_path in paths:
                record = {'guest_path': guest_path}
                try:
                    inode, data = filesystem.lookup(guest_path)
                    extract = HERE / 'guest_source_extracts' / name / guest_path.lstrip('/')
                    extract.parent.mkdir(parents=True, exist_ok=True)
                    with extract.open('xb') as stream:
                        stream.write(data)
                    record.update(present=True, inode=inode, bytes=len(data),
                                  sha256=hashlib.sha256(data).hexdigest(),
                                  extracted_path=str(extract.relative_to(HERE)))
                except FileNotFoundError:
                    record.update(present=False)
                row['files'].append(record)
            row['virtual_blocks_read'] = len(disk.cache)
        row['sha256_after'] = sha(image)
        row['image_unchanged'] = row['sha256_before'] == row['sha256_after']
        report['images'].append(row)
    with (HERE / 'GUEST_SOURCE_INSPECTION.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
