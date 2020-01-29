import bitstring
import binascii

a = bitstring.BitArray('0b000001000100101101010111011100001010010000000000000000000000110111001000110111100001101000011100011101110010011111101011110000110101010111010000000000001000011000011011')
#print(a)
for i in range(0xffff):
    crc = bin(i)[2:].zfill(16)
    crc = '0b' + crc
    #print(crc)
    j = a + crc
    #print(j)
    if (binascii.crc_hqx(j.bytes, 0xffff) == 0x1d0f):
        print(crc)
        break 
		