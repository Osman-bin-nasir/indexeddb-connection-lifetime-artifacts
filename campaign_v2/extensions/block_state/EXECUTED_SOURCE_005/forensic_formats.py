"""Non-mutating SQLite/WAL structural observations. No recovery/loss inference."""
import hashlib
from pathlib import Path
import struct


def checksum(data, order, initial=(0,0)):
    if len(data)%8:
        raise ValueError('SQLite WAL checksum requires whole pairs of words')
    s0,s1=initial
    for a,b in struct.iter_unpack(order+'II',data):
        s0=(s0+a+s1)&0xffffffff
        s1=(s1+b+s0)&0xffffffff
    return s0,s1


def inspect(path):
    data=Path(path).read_bytes()
    result={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
            'format':'unavailable_or_non_sqlite','target_page_interpretation':'not established'}
    if data.startswith(b'SQLite format 3\0') and len(data)>=100:
        n=struct.unpack('>H',data[16:18])[0]
        size=65536 if n==1 else n
        result.update(format='sqlite_database',page_size=size,logical_page_count=struct.unpack('>I',data[28:32])[0],
                      physical_pages=len(data)//size if size else None,
                      trailing_bytes=len(data)%size if size else None,
                      file_change_counter=struct.unpack('>I',data[24:28])[0],
                      read_version=data[19],write_version=data[18])
    elif len(data)>=32 and struct.unpack('>I',data[:4])[0] in (0x377f0682,0x377f0683):
        magic,version,size,sequence,salt0,salt1,c0,c1=struct.unpack('>8I',data[:32])
        order='<' if magic==0x377f0682 else '>'
        current=checksum(data[:24],order)
        frames=[]
        if size<512 or size>65536 or size&(size-1):
            return {**result,'format':'sqlite_wal','error':'invalid_page_size'}
        stride=24+size
        valid_prefix=current==(c0,c1)
        for offset in range(32,len(data)-stride+1,stride):
            page,commit,s0,s1,x0,x1=struct.unpack('>6I',data[offset:offset+24])
            current=checksum(data[offset:offset+8]+data[offset+24:offset+stride],order,current)
            match=current==(x0,x1) and (s0,s1)==(salt0,salt1)
            valid_prefix=valid_prefix and match
            frames.append({'offset':offset,'page_number':page,'commit_database_pages':commit,
                           'salt_matches':(s0,s1)==(salt0,salt1),'checksum_valid':current==(x0,x1),
                           'valid_prefix':valid_prefix,
                           'page_sha256':hashlib.sha256(data[offset+24:offset+stride]).hexdigest()})
        result.update(format='sqlite_wal',version=version,page_size=size,checkpoint_sequence=sequence,
                      header_checksum_valid=checksum(data[:24],order)==(c0,c1),frames=frames,
                      trailing_bytes=(len(data)-32)%stride,
                      interpretation='Structural WAL frames only; no target serialization or fault-instant attribution')
    elif data[:8]==bytes.fromhex('d9d505f920a163d7'):
        result.update(format='sqlite_rollback_journal',parse_status='header observed; record interpretation unavailable')
    return result
