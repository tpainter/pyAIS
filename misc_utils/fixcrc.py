import binascii
import sys

import bitstring


def crc_remainder(input_bitstring, polynomial_bitstring, initial_filler):
    '''
    Calculates the CRC remainder of a string of bits using a chosen polynomial.
    initial_filler should be '1' or '0'.
    '''
    len_input = len(input_bitstring)
    initial_padding = initial_filler * (len(polynomial_bitstring) - 1)
    input_padded_array = list(input_bitstring + initial_padding)
    polynomial_bitstring = polynomial_bitstring.lstrip('0')
    while '1' in input_padded_array[:len_input]:
        cur_shift = input_padded_array.index('1')
        for i in range(len(polynomial_bitstring)):
            if polynomial_bitstring[i] == input_padded_array[cur_shift + i]:
                input_padded_array[cur_shift + i] = '0'
            else:
                input_padded_array[cur_shift + i] = '1'
    return ''.join(input_padded_array)[len_input:]

# https://www.lammertbies.nl/forum/viewtopic.php?t=1847
def crc16(msg, poly = '0x1021', initial = '0xffff', invert=True, swap_bytes = False):
    """
    returns crc16
    
    poly = 0x1021 0x8408 0x811 0x8810
    """
    len_input = len(msg)
    poly_bits = bitstring.BitArray(hex=poly)
    poly_bits.prepend('0b1') #assumed
    
    print(msg.bin)
    if swap_bytes:
        a = msg.byteswap('>h')
    print(msg.bin)
        
    
    ini = msg[:len(poly_bits)-1] ^ bitstring.BitArray(hex='0xffff')
    msg.overwrite(ini , 0)
    
    padding = '0' * (len(poly_bits) - 1)
    pad_bits = bitstring.BitArray(bin=padding)
    msg.append(pad_bits)
    
    while msg[:len_input].any(1):
        cur_shift = msg.find('0b1')[0]
        for j in range(len(poly_bits)):
            if poly_bits[j] == msg[cur_shift + j]:
                msg.set(False, cur_shift + j)
            else:
                msg.set(True, cur_shift + j)
    if invert:
        return msg[len_input:] ^ bitstring.BitArray('0xffff')
    else:
        return msg[len_input:]
    

if __name__ == "__main__":
    
    z = bitstring.BitArray("0b00000000000000000001110100001111")
    y = bitstring.BitArray("0b00000000000000000000000000000000")
    x = bitstring.BitArray("0b01101011111111111111111111111111")
    trial  = bitstring.BitArray("0b0000010001001011010101110111000010100100000000000000000000001101110010001101111000011010000111000111011100100111111010111100001101010101110100000000000010000110000110111011110111000011")
    trial2 = bitstring.BitArray("0b000001100100101101010111011100001010010000000000000000000000110111001000110111100001101000011100011101110010011111101011110000110101010111010000000000001000011000011011")
    
    l = len(trial)
    correction_table = {}
    #create error check table
    for i in range(l):
        a = "0b"
        for _ in range(l):
            if _ == i:
                a += '1'
            else:
                a += '0'
        #print(a)
        temp = bitstring.BitArray(bin=a)
        #print(binascii.crc_hqx(temp.bytes, 0xffff))
        correction_table[binascii.crc_hqx(temp.bytes, 0xffff)] = i
    
    print(hex(binascii.crc_hqx(b'123456789', 0xffff)))
    print(bin(binascii.crc_hqx(x.bytes, 0xffff))[2:])
    #print(x.hex)
    print(crc_remainder('6bffffff', '0x8408', '1'))
    
    sys.exit()
    
    if (binascii.crc_hqx(trial.bytes, 0xffff) == 0x1d0f):
        pass
        #print("Good")
    
    print(crc16(x).bin)
    