# -*- coding: utf-8 -*-
import socket
import asyncio
import struct
import signal
import sys

"""
```shell
    ip link set lo mtu 1500
```
"""

__MULTIPLIER = 5000
__DATAGRAM = b"\xba\xdc\x0f\xfe" * __MULTIPLIER
ETH_P_ALL= 3
ETH_P_IP = 0x0800
DEST_ADDR = "127.0.0.1"
FLAGS_DF = 1 << 15
FLAGS_MF = 1 << 14
MTU_LIMIT = 1500
no_pkt_sent = 0
no_pkt_recv = 0

packets = {}

def sigint_handler(sig, frame):
    global no_pkt_sent
    global no_pkt_recv
    print("\nPING INTERROMPIDO\n- pacotes enviados: %d\n- pacotes recebidos: %d\n- perda: %.2f%%" \
        % (no_pkt_sent, no_pkt_recv, 100*(no_pkt_sent - no_pkt_recv)/no_pkt_sent))
    sys.exit(0)


class Header:
    def __init__(self, packet):
        version_ihl, _, total_length, ident, flags_offset, ttl, protocol, chksum = struct.unpack('!BBHHHBBH', packet[:12])
        self.version = version_ihl >> 4
        self.ihl = version_ihl & 0xF
        self.length = total_length
        self.id = ident
        self.flags = flags_offset >> 13
        self.offset = flags_offset & 0x1FFF
        self.ttl = ttl
        self.protocol = protocol
        self.checksum = chksum
        self.src_ip = addr2str(packet[12:16])
        self.dst_ip = addr2str(packet[16:20])
        

class Packet:
    def __init__(self, id_pkt, header, data):
        self.id = id_pkt
        self.header = header
        self.data = data 


def addr2str(addr):
    return '%d.%d.%d.%d' % tuple(int(x) for x in addr)


def str2addr(addr):
    return bytes(int(x) for x in addr.split('.'))


def calc_checksum(segment):
    if len(segment) % 2 == 1:
        # se for ímpar, faz padding à direita
        segment += b"\x00"
    checksum = 0
    for i in range(0, len(segment), 2):
        x, = struct.unpack('!H', segment[i:i+2])
        checksum += x
        while checksum > 0xffff:
            checksum = (checksum & 0xffff) + 1
    checksum = ~checksum
    return checksum & 0xffff


def timeout(packets, pkt_id):
    if pkt_id in packets:
        del packets[pkt_id]


def send_ping(send_fd):
    global no_pkt_sent
    # Exemplo de pacote ping (ICMP echo request) destinado a 1.1.1.1.
    # Veja que como estamos montando o cabeçalho IP, precisamos preencher
    # endereço IP de origem e de destino.
    msg = bytearray(b"\x08\x00\x00\x00" + __DATAGRAM)
    msg[2:4] = struct.pack('!H', calc_checksum(msg))

    no_pkt_sent += 1

    print('[S] pkt %d, enviando ping: %d bytes' % (no_pkt_sent, len(msg)))

    send_fd.sendto(msg, (DEST_ADDR, 0))

    asyncio.get_event_loop().call_later(1, send_ping, send_fd)


def raw_recv(recv_fd):
    global no_pkt_recv
    packet = recv_fd.recv(20000)

    header = Header(packet)
    pkt_id = (header.src_ip, header.dst_ip, header.protocol, header.id)
    data = packet[header.ihl * 4:]
    pkt = Packet(pkt_id, header, data)

    # verifica se é um pacote ipv4
    if not pkt.header.version == 4: 
        return
    # verifica se é uma resposta ao ping
    if pkt.header.src_ip != DEST_ADDR:
        return
    # adiciona pacote à lista de pacotes
    if pkt.id not in packets:
        packets[pkt.id] = {'pkts': [pkt], data: pkt.data, 'hits':1, 'timer': None, 'data': b''}
        packets[pkt.id]['timer'] = asyncio.get_event_loop().call_later(pkt.header.ttl, timeout, packets, pkt.id)
    else:
        packets[pkt.id]['pkts'].append(pkt)
        packets[pkt.id]['data'] += pkt.data
        packets[pkt.id]['hits'] += 1
    print("[R] recebendo resposta: %s -> %s, %d bytes, %d hits" % \
        (pkt.header.src_ip, pkt.header.dst_ip, len(packet), packets[pkt.id]['hits']))

    # contabiliza no ultimo fragmento
    if len(packet) < MTU_LIMIT:
        no_pkt_recv += 1

    # caso tenha terminado de montar o pacote antes do timeout
    if (pkt.header.flags & FLAGS_MF) == 0 and pkt.header.offset > 0 and packets[pkt.id]['timer'] is not None:
        packets[pkt.id]['timer'].cancel()
    
def main(argv=None):
    global DEST_ADDR

    if len(argv) > 2:
        print(argv[0], "\nUso:\n\tsudo python ip.py [DEST_IP]?")
        return 0

    elif len(argv) == 2:
        DEST_ADDR = argv[1]

    # Ver a manpage http://man7.org/linux/man-pages/man7/raw.7.html,
    send_fd = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)

    # Para receber existem duas abordagens. A primeira é a da etapa anterior
    # do trabalho, de colocar socket.IPPROTO_TCP, socket.IPPROTO_UDP ou
    # socket.IPPROTO_ICMP. Assim ele filtra só datagramas IP que contenham um
    # segmento TCP, UDP ou mensagem ICMP, respectivamente, e permite que esses
    # datagramas sejam recebidos. No entanto, essa abordagem faz com que o
    # próprio sistema operacional realize boa parte do trabalho da camada IP,
    # como remontar datagramas fragmentados. Para que essa questão fique a
    # cargo do nosso programa, é necessário uma outra abordagem: usar um socket
    # de camada de enlace, porém pedir para que as informações de camada de
    # enlace não sejam apresentadas a nós, como abaixo. Esse socket também
    # poderia ser usado para enviar pacotes, mas somente se eles forem quadros,
    # ou seja, se incluírem cabeçalhos da camada de enlace.
    recv_fd = socket.socket(socket.AF_PACKET, socket.SOCK_DGRAM, socket.htons(ETH_P_ALL))

    loop = asyncio.get_event_loop()
    loop.add_reader(recv_fd, raw_recv, recv_fd)
    asyncio.get_event_loop().call_later(1, send_ping, send_fd)
    loop.run_forever()

if __name__ == '__main__':    
    signal.signal(signal.SIGINT, sigint_handler)
    main(sys.argv)
    signal.pause()
