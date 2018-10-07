#!/usr/bin/python3
#
# Antes de usar, execute o seguinte comando para evitar que o Linux feche
# as conexões TCP abertas por este programa:
#
# sudo iptables -I OUTPUT -p tcp --tcp-flags RST RST -j DROP
#

import asyncio
import socket
import struct

FLAGS_FIN = 1<<0
FLAGS_SYN = 1<<1
FLAGS_RST = 1<<2
FLAGS_ACK = 1<<4


def addr2str(addr):
    return '%d.%d.%d.%d' % tuple(int(x) for x in addr)


def str2addr(addr):
    return bytes(int(x) for x in addr.split('.'))


def handle_ipv4_header(packet):
    version = packet[0] >> 4
    ihl = packet[0] & 0xf
    assert version == 4
    src_addr = addr2str(packet[12:16])
    dst_addr = addr2str(packet[16:20])
    segment = packet[4*ihl:]
    return src_addr, dst_addr, segment


def make_synack(src_port, dst_port, ack_no):
    return struct.pack('!HHIIHHHH', src_port, dst_port, 0,
                       ack_no, (5<<12)|FLAGS_ACK|FLAGS_SYN,
                       1024, 0, 0)


def calc_checksum(segment):
    checksum = 0
    for i in range(0, len(segment), 2):
        x, = struct.unpack('!H', segment[i:i+2])
        checksum += x
        while checksum > 0xffff:
            checksum = (checksum & 0xffff) + 1
    checksum = ~checksum
    return checksum & 0xffff


def fix_checksum(segment, src_addr, dst_addr):
    pseudohdr = str2addr(src_addr) + str2addr(dst_addr) + \
        struct.pack('!HH', 0x0006, len(segment))
    seg = bytearray(segment)
    seg[16:18] = b'\x00\x00'
    seg[16:18] = struct.pack('!H', calc_checksum(pseudohdr + seg))
    return bytes(seg)


def timer_test(src_addr, src_port):
    print('5 segundos desde que aceitamos a conexão de %s:%d' %
          (src_addr, src_port))


def raw_recv(fd):
    packet = fd.recv(12000)
    src_addr, dst_addr, segment = handle_ipv4_header(packet)
    src_port, dst_port, seq_no, ack_no, \
        flags, window_size, checksum, urg_ptr = \
        struct.unpack('!HHIIHHHH', segment[:20])

    if dst_port != 7000:
        return

    if (flags & FLAGS_SYN) == FLAGS_SYN:
        print('%s:%d -> %s:%d (seq=%d)' % (src_addr, src_port,
                                           dst_addr, dst_port, seq_no))
        
        fd.sendto(fix_checksum(make_synack(dst_port, src_port, seq_no + 1),
                               src_addr, dst_addr),
                  (src_addr, src_port))

        asyncio.get_event_loop().call_later(5, timer_test, src_addr, src_port)


fd = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_TCP)
loop = asyncio.get_event_loop()
loop.add_reader(fd, raw_recv, fd)
loop.run_forever()
