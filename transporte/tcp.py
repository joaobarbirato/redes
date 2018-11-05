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
import os
import random

FLAGS_FIN = 1 << 0
FLAGS_SYN = 1 << 1
FLAGS_RST = 1 << 2
FLAGS_ACK = 1 << 4

MSS = 1460

TESTAR_PERDA_ENVIO = False


class Conexao:
    def __init__(self, id_conexao, seq_no, ack_no, rtt=3):
        self.id_conexao = id_conexao
        self.seq_no = seq_no
        self.ack_no = ack_no
        self.send_queue = b"HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\n\r\n" + \
            1000000 * b"hello pombo\n"
        self.rtt = rtt
        self.nao_confirmado = []
        self.timer = None


conexoes = {}


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
    segment = packet[4 * ihl:]
    return src_addr, dst_addr, segment


def make_synack(src_port, dst_port, seq_no, ack_no):
    return struct.pack('!HHIIHHHH', src_port, dst_port, seq_no,
                       ack_no, (5 << 12) | FLAGS_ACK | FLAGS_SYN,
                       1024, 0, 0)


def calc_checksum(segment):
    if len(segment) % 2 == 1:
        # se for ímpar, faz padding à direita
        segment += b'\x00'
    checksum = 0
    for i in range(0, len(segment), 2):
        x, = struct.unpack('!H', segment[i:i + 2])
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


def send_next(fd, conexao):
    payload = conexao.send_queue[:MSS]
    conexao.send_queue = conexao.send_queue[MSS:]

    (dst_addr, dst_port, src_addr, src_port) = conexao.id_conexao

    segment = struct.pack('!HHIIHHHH', src_port, dst_port, conexao.seq_no,
                          conexao.ack_no, (5 << 12) | FLAGS_ACK,
                          1024, 0, 0) + payload

    # Colocando o pacote que sera enviado na fila de nao confirmados, para confirmar seu ack futuramente
    conexao.nao_confirmado.append(segment)

    conexao.seq_no = (conexao.seq_no + len(payload)) & 0xffffffff

    segment = fix_checksum(segment, src_addr, dst_addr)

    if not TESTAR_PERDA_ENVIO or random.random() < 0.95:
        fd.sendto(segment, (dst_addr, dst_port))
        conexao.timer = asyncio.get_event_loop().call_later(conexao.rtt, timeout, fd, conexao, segment)

    if conexao.send_queue == b"":
        segment = struct.pack('!HHIIHHHH', src_port, dst_port, conexao.seq_no,
                              conexao.ack_no, (5 << 12) | FLAGS_FIN | FLAGS_ACK,
                              0, 0, 0)
        segment = fix_checksum(segment, src_addr, dst_addr)
        fd.sendto(segment, (dst_addr, dst_port))


#fazer com que essa funcao soh envie em caso de timeout
def timeout(fd, conexao, segment):
    (dst_addr, dst_port, src_addr, src_port) = conexao.id_conexao
    if not TESTAR_PERDA_ENVIO or random.random() < 0.95:
        fd.sendto(segment, (dst_addr, dst_port))
    # conexao.timer = asyncio.get_event_loop().call_later(conexao.rtt, timeout, fd, conexao)


def raw_recv(fd):
    packet = fd.recv(12000)
    src_addr, dst_addr, segment = handle_ipv4_header(packet)
    src_port, dst_port, seq_no, ack_no, flags, window_size, checksum, urg_ptr = struct.unpack(
        '!HHIIHHHH', segment[:20])

    id_conexao = (src_addr, src_port, dst_addr, dst_port)

    if dst_port != 7000:
        return

    payload = segment[4 * (flags >> 12):]

    if (flags & FLAGS_SYN) == FLAGS_SYN:
        print('%s:%d -> %s:%d (seq=%d)' % (src_addr, src_port,
                                           dst_addr, dst_port, seq_no))

        conexoes[id_conexao] = conexao = Conexao(id_conexao=id_conexao,
                                                 seq_no=struct.unpack(
                                                     'I', os.urandom(4))[0],
                                                 ack_no=seq_no + 1)

        fd.sendto(fix_checksum(make_synack(dst_port, src_port, conexao.seq_no, conexao.ack_no),
                               src_addr, dst_addr),
                               (src_addr, src_port))

        conexao.seq_no += 1
        asyncio.get_event_loop().call_later(.1, send_next, fd, conexao)

    elif id_conexao in conexoes:
        conexao = conexoes[id_conexao]
        if (flags & FLAGS_ACK) == FLAGS_ACK:
            received_ack(fd, ack_no, seq_no, conexao)
        conexao.ack_no += len(payload)
        asyncio.get_event_loop().call_later(.1, send_next, fd, conexao)
    else:
        print('%s:%d -> %s:%d (pacote associado a conexão desconhecida)' %
              (src_addr, src_port, dst_addr, dst_port))


def received_ack(fd, ack_no, seq_no, conexao):
    for segmento in conexao.nao_confirmado:
        src_port, dst_port, seq_no_segmento, ack_no_segmento, flags, window_size, checksum, urg_ptr = struct.unpack(
        '!HHIIHHHH', segmento[:20])
        if seq_no == ack_no_segmento:
            #print('Confirmado ack = %d' % seq_no)
            conexao.nao_confirmado.remove(segmento)
            if conexao.timer is not None:
                print('timercancelado')
                conexao.timer.cancel()
            return


if __name__ == '__main__':
    fd = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_TCP)
    loop = asyncio.get_event_loop()
    loop.add_reader(fd, raw_recv, fd)
    loop.run_forever()
