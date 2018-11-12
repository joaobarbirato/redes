#!/usr/bin/python3
#
# Antes de usar, execute o seguinte comando para evitar que o Linux feche
# as conexões TCP abertas por este programa:
#
# sudo iptables -I OUTPUT -p tcp --tcp-flags RST RST -j DROP
#

"""
    Grupo                               RA
        Cassiano Maia                       726507
        Gabriel de Souza Alves              726515
        Joao Gabriel Melo Barbirato         726546
        Julia Milani                        726552
"""

import asyncio
import socket
import struct
import os
from collections import deque
from datetime import datetime

FLAGS_FIN = 1 << 0
FLAGS_SYN = 1 << 1
FLAGS_RST = 1 << 2
FLAGS_ACK = 1 << 4

MSS = 1460


class Conexao:
    def __init__(self, id_conexao, seq_no, ack_no):
        self.id_conexao = id_conexao
        self.seq_no = seq_no
        self.ack_no = ack_no
        self.rtt = 3
        self.new_time = None
        self.timer = None
        self.send_queue = b"HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\n\r\n" + 1000000 * b"hello pombo\n"
        self.not_acked_queue = deque()
        self.acks = {}
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


def ack_recv(fd, conexao, ack_no):
    # ack_no da Conexão é o SendBase
    # Atualiza o SendBase, descarta segmentos com seq_no < SendBase
    if ack_no > conexao.ack_no:
        conexao.ack_no = ack_no
        sorted(conexao.not_acked_queue, key=lambda x: x[1])
        while conexao.not_acked_queue[0][1] < ack_no:
            conexao.not_acked_queue.popleft()
    # Existem pacotes não-confirmados
    if len(conexao.not_acked_queue) >= 1:
        conexao.timer = asyncio.get_event_loop().call_later(conexao.rtt, timeout, 
                                                            fd, conexao)
    elif conexao.timer is not None:
        conexao.timer.cancel()
        new_rtt = datetime.now() - conexao.new_time
        conexao.rtt = new_rtt.total_seconds()
        conexao.new_time = None
    # ACK duplicado recebido para o segmento ack_no
    else:
        if ack_no in conexao.acks:
            conexao.acks[ack_no] += 1
        else:
            conexao.acks[ack_no] = 1
        # Faz o envio imediato do segmento ack_no
        if conexao.acks[ack_no] == 3:
            (dst_addr, dst_port, _, _) = conexao.id_conexao
            segment = [segm for segm in conexao.not_acked_queue if segm[1] == ack_no][0][0]
            fd.sendto(segment, (dst_addr, dst_port))


def timeout(fd, conexao):
    (dst_addr, dst_port, _, _) = conexao.id_conexao
    # Envia o segmento com o menor seq_no
    segment = conexao.not_acked_queue[0][0]
    fd.sendto(segment, (dst_addr, dst_port))
    # Inicia o timer
    conexao.timer = asyncio.get_event_loop().call_later(conexao.rtt, 
                                                timeout, fd, conexao)


def send_next(fd, conexao):
    payload = conexao.send_queue[:MSS]
    conexao.send_queue = conexao.send_queue[MSS:]

    (dst_addr, dst_port, src_addr, src_port) = conexao.id_conexao

    segment = struct.pack('!HHIIHHHH', src_port, dst_port, conexao.seq_no,
                          conexao.ack_no, (5 << 12) | FLAGS_ACK,
                          1024, 0, 0) + payload

    # Atualiza o NextSeqNum
    seq_no = conexao.seq_no
    conexao.seq_no = (conexao.seq_no + len(payload)) & 0xffffffff
    segment = fix_checksum(segment, src_addr, dst_addr)
    
    # Coloca o segmento na fila de não-confirmados
    conexao.not_acked_queue.append([segment, seq_no])
    fd.sendto(segment, (dst_addr, dst_port))
    
    # Começa o timer para retransmissão
    if conexao.timer is not None:
        conexao.timer = asyncio.get_event_loop().call_later(conexao.rtt, timeout, 
                                                            fd, conexao)
        conexao.new_time = datetime.now()
    if conexao.send_queue == b"":
        segment = struct.pack('!HHIIHHHH', src_port, dst_port, conexao.seq_no,
                          conexao.ack_no, (5<<12)|FLAGS_FIN|FLAGS_ACK,
                          0, 0, 0)
        segment = fix_checksum(segment, src_addr, dst_addr)
        fd.sendto(segment, (dst_addr, dst_port))
        print("Pacote final enviado")
    else:
        asyncio.get_event_loop().call_later(.001, send_next, fd, conexao)


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
            ack_recv(fd, conexao, ack_no)
    else:
        print('%s:%d -> %s:%d (pacote associado a conexão desconhecida)' %
              (src_addr, src_port, dst_addr, dst_port))


if __name__ == '__main__':
    sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_TCP)
    loop = asyncio.get_event_loop()
    loop.add_reader(sock, raw_recv, sock)
    loop.run_forever()

