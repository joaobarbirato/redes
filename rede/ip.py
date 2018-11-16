# -*- coding: utf-8 -*-
import socket
import asyncio
import struct

"""
```shell
    ip link set lo mtu 1500
```
"""

__MULTIPLIER = 360
__DATAGRAM = b"\xba\xdc\x0f\xfe" * __MULTIPLIER
ETH_P_IP = 0x0800
DEST_ADDR = "1.1.1.1"
FLAGS_DF = 1 << 15
FLAGS_MF = 1 << 14
packets = {}

class Packet:
    def __init__(self, id_pkt, offset, data, content=""):
        self.id = id_pkt
        self.fragments = {offset:data}
        self.content = content 


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


def send_ping(send_fd):
    # Exemplo de pacote ping (ICMP echo request) destinado a 1.1.1.1.
    # Veja que como estamos montando o cabeçalho IP, precisamos preencher
    # endereço IP de origem e de destino.
    msg = bytearray(b"\x08\x00\x00\x00" + __DATAGRAM)
    msg[2:4] = struct.pack('!H', calc_checksum(msg))
    print('enviando ping: %d' % len(msg))
    send_fd.sendto(msg, (DEST_ADDR, 0))

    asyncio.get_event_loop().call_later(1, send_ping, send_fd)


def raw_recv(recv_fd):
    packet = recv_fd.recv(12000)
    
    version_ihl_trash, total_length, ident, flags_fragoffset, ttl_proto, chksum = struct.unpack('!HHHHHH', packet[:12])
    src_ip = addr2str(packet[12:16])
    dst_ip = addr2str(packet[16:20])
    
    # verifica se é um pacote ipv4
    if not version_ihl_trash >> 12 == 4: 
        return
    # verifica se é uma resposta ao ping
    if src_ip != DEST_ADDR:
        return

    print("%s -> %s" % (src_ip, dst_ip))

    if (flags_fragoffset & FLAGS_DF) == FLAGS_DF:
        print("DO NOT FRAGMENT")
    if (flags_fragoffset & FLAGS_MF) == FLAGS_MF:
        print(f"ID {ident} NEEDS MORE FRAGMENTS")
    frag_offset = flags_fragoffset & 0x1FFF
    if frag_offset is not 0:
        print("Offset: %d" % frag_offset)
    
    if str(ident) not in packets:
        packets[str(ident)] = {'pkt':packet, 'hits':1}
    else:
        packets[str(ident)]['pkt'] += packet
        packets[str(ident)]['hits'] += 1

    #[print("ID: ", key," HITS: ", value['hits'], end=", ") for key, value in packets.items()]
    #print()


if __name__ == '__main__':
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
    recv_fd = socket.socket(socket.AF_PACKET, socket.SOCK_DGRAM, socket.htons(ETH_P_IP))

    loop = asyncio.get_event_loop()
    loop.add_reader(recv_fd, raw_recv, recv_fd)
    asyncio.get_event_loop().call_later(1, send_ping, send_fd)
    loop.run_forever()
