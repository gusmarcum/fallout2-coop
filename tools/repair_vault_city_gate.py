#!/usr/bin/env python3
"""Repair a saved Vault City Downtown map (VCTYDWTN.SAV) whose inner gate refuses every
walk with "You cannot get there" although the guard opened it.

The gate script (VIEntDor) drops an invisible Secret Blocking Hex (pid 0x02000043) on the
gate's approach tile 28917 at every map entry and destroys it five game ticks later from a
timer. When that timer is lost before it fires, the blocker survives in the map's .SAV and
stacks up on later visits; the script's cleanup removes only one per call, so the tile stays
walled off for good. See bugs/008-vault-city-gate-blocker.md.

This tool deletes those records from the save. It parses the whole object list with the
engine's record layout (object.cc objectRead, proto.cc objectDataRead, recursive
inventories), requires the parse to consume the file to its last byte before it changes
anything, fixes the total and elevation-0 object counts, parses the result again, and keeps
a .bak next to every file it rewrites. Item and scenery subtypes come from the game's proto
files in patch000.dat / master.dat.

usage:
  repair_vault_city_gate.py --world <game dir>              every slot's VCTYDWTN.SAV + data/MAPS
  repair_vault_city_gate.py [--game <game dir>] <VCTYDWTN.SAV> [more ...]
  add --check to report only

The game dir is the one holding master.dat (and data/SAVEGAME). Without --game it is
derived from the save path (<game>/data/SAVEGAME/SLOTxx/VCTYDWTN.SAV or <game>/data/MAPS/...).
"""
import glob
import gzip
import os
import shutil
import struct
import sys
import zlib

TILE, PID_BLOCKER = 28917, 0x02000043
FIRST_EXIT_GRID_PID, LAST_EXIT_GRID_PID = 0x5000010, 0x5000017
BS = chr(92)


def dat_tree(path):
    f = open(path, 'rb')
    f.seek(0, 2)
    size = f.tell()
    f.seek(size - 8)
    tree_size, file_size = struct.unpack('<II', f.read(8))
    f.seek(file_size - tree_size - 8)
    count = struct.unpack('<I', f.read(4))[0]
    ents = {}
    for _ in range(count):
        n = struct.unpack('<I', f.read(4))[0]
        name = f.read(n).decode('latin1').lower().replace(BS, '/')
        comp, real, packed, off = struct.unpack('<BIII', f.read(13))
        ents[name] = (comp, real, packed, off)
    return f, ents


_proto_types = {}


def proto_types(game_dir):
    """pid -> subtype (item.type / scenery.type) for every item and scenery proto, indexed by
    the pid stored inside each .pro; patch000.dat overrides master.dat."""
    if game_dir in _proto_types:
        return _proto_types[game_dir]
    types = {}
    dats = [os.path.join(game_dir, n) for n in ('master.dat', 'patch000.dat')]
    dats = [d for d in dats if os.path.exists(d)]
    if not dats:
        raise ValueError('no master.dat in ' + game_dir + ' (use --game)')
    for dat in dats:  # master first, patch overrides
        f, ents = dat_tree(dat)
        for name, (comp, real, packed, off) in ents.items():
            if not (name.startswith('proto/items/') or name.startswith('proto/scenery/')) or not name.endswith('.pro'):
                continue
            f.seek(off)
            d = f.read(packed)
            if comp:
                d = zlib.decompress(d)
            if len(d) >= 36:
                pid, sub = struct.unpack('>i', d[0:4])[0], struct.unpack('>i', d[32:36])[0]
                types[pid & 0xFFFFFFFF] = sub
    _proto_types[game_dir] = types
    return types


class Walker:
    def __init__(self, data, version, types):
        self.d = data
        self.version = version
        self.types = types

    def be(self, o):
        return struct.unpack('>i', self.d[o:o + 4])[0]

    def record(self, pos):
        """Return (end_pos, info) for the object record starting at pos."""
        d = self.d
        if pos + 84 > len(d):
            raise ValueError('record runs past end at %d' % pos)
        tile, elev, pid = self.be(pos + 4), self.be(pos + 40), self.be(pos + 44)
        flags = self.be(pos + 36)
        inv_len = self.be(pos + 72)
        p = pos + 84
        ptype = (pid >> 24) & 0xFF
        upid = pid & 0xFFFFFFFF
        if ptype == 1:  # critter: field_0 + 7 combat ints + hp/radiation/poison
            p += 4 + 28 + 12
        else:
            p += 4  # data.flags
            if ptype == 0:  # item
                sub = self.types.get(upid)
                if sub is None:
                    raise ValueError('unknown item proto 0x%08X at %d' % (upid, pos))
                p += {3: 8, 4: 4, 5: 4, 6: 4}.get(sub, 0)  # weapon, ammo, misc, key
            elif ptype == 2:  # scenery
                sub = self.types.get(upid)
                if sub is None:
                    raise ValueError('unknown scenery proto 0x%08X at %d' % (upid, pos))
                if sub == 0:  # door
                    p += 4
                elif sub in (1, 2):  # stairs, elevator
                    p += 8
                elif sub in (3, 4):  # ladders
                    p += 4 if self.version == 19 else 8
            elif ptype == 5 and FIRST_EXIT_GRID_PID <= upid <= LAST_EXIT_GRID_PID:
                p += 16
        if inv_len < 0 or inv_len > 100000:
            raise ValueError('bad inventory length %d at %d' % (inv_len, pos))
        for _ in range(inv_len):
            p += 4  # quantity
            p, _sub = self.record(p)
        return p, (pos, tile, elev, upid, flags)

    def walk(self, start):
        pos = start
        total = self.be(pos)
        pos += 4
        if total < 0 or total > 100000:
            raise ValueError('bad total')
        recs = []
        counts = []
        for _elev in range(3):
            cnt_off = pos
            cnt = self.be(pos)
            pos += 4
            if cnt < 0 or cnt > total:
                raise ValueError('bad elevation count')
            counts.append((cnt_off, cnt))
            for _ in range(cnt):
                s = pos
                pos, info = self.record(pos)
                recs.append((s, pos, info))
        if pos != len(self.d):
            raise ValueError('parse ended at %d, file is %d' % (pos, len(self.d)))
        if sum(c for _, c in counts) != total:
            raise ValueError('counts do not add up')
        return recs, counts, total


def find_section(w):
    """The object section is the tail of the file: the [total][count0][record...] start
    whose parse consumes the file exactly."""
    d = w.d
    for pos in range(236, len(d) - 96, 4):
        total = w.be(pos)
        c0 = w.be(pos + 4)
        if not (0 < total <= 100000 and 0 <= c0 <= total):
            continue
        tile = w.be(pos + 8 + 4)
        elev = w.be(pos + 8 + 40)
        pid = w.be(pos + 8 + 44)
        if not (0 <= tile < 40000 and elev == 0 and 0 <= (pid >> 24) <= 6):
            continue
        try:
            recs, counts, tot = w.walk(pos)
            return pos, recs, counts, tot
        except (ValueError, struct.error):
            continue
    raise ValueError('object section not found')


def game_dir_for(path, override):
    if override:
        return override
    p = os.path.abspath(path).replace(BS, '/')
    for marker in ('/data/SAVEGAME/', '/data/MAPS/', '/data/maps/', '/data/savegame/'):
        i = p.lower().find(marker.lower())
        if i >= 0:
            return p[:i]
    return os.path.dirname(os.path.dirname(p))


def repair(path, check_only, game_override):
    raw = open(path, 'rb').read()
    gz = raw[:2] == b'\x1f\x8b'
    data = bytearray(gzip.decompress(raw) if gz else raw)
    version = struct.unpack('>i', data[0:4])[0]
    types = proto_types(game_dir_for(path, game_override))
    w = Walker(bytes(data), version, types)
    start, recs, counts, total = find_section(w)
    stale = [(s, e) for (s, e, (pos, tile, elev, pid, flags)) in recs if tile == TILE and elev == 0 and pid == PID_BLOCKER]
    print('%-60s objects %d, stale gate blockers %d%s' % (path, total, len(stale), ' (check only)' if check_only else ''))
    if check_only or not stale:
        return len(stale)
    out = bytearray(data)
    for s, e in sorted(stale, reverse=True):
        del out[s:e]
    cnt0_off, cnt0 = counts[0]
    struct.pack_into('>i', out, start, total - len(stale))
    struct.pack_into('>i', out, cnt0_off, cnt0 - len(stale))
    w2 = Walker(bytes(out), version, types)
    start2, recs2, counts2, total2 = find_section(w2)
    left = [1 for (_s, _e, (pos, tile, elev, pid, flags)) in recs2 if tile == TILE and elev == 0 and pid == PID_BLOCKER]
    assert start2 == start and total2 == total - len(stale) and not left, 'post-repair parse failed'
    shutil.copyfile(path, path + '.bak')
    open(path, 'wb').write(gzip.compress(bytes(out)) if gz else bytes(out))
    print('    removed %d record(s); %d objects remain; verified' % (len(stale), total2))
    return len(stale)


def main(argv):
    check_only = '--check' in argv
    args = [a for a in argv if a != '--check']
    game_override = None
    if '--game' in args:
        i = args.index('--game')
        game_override = args[i + 1]
        del args[i:i + 2]
    if args and args[0] == '--world':
        world = args[1]
        game_override = game_override or world
        paths = glob.glob(os.path.join(world, 'data', 'SAVEGAME', 'SLOT*', 'VCTYDWTN.SAV'))
        paths += glob.glob(os.path.join(world, 'data', 'MAPS', 'VCTYDWTN.SAV'))
    else:
        paths = args
    if not paths:
        print(__doc__)
        return 2
    rc = 0
    for p in sorted(paths):
        try:
            repair(p, check_only, game_override)
        except Exception as e:  # report and go on with the next file
            print('%-60s FAILED: %s' % (p, e))
            rc = 1
    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
