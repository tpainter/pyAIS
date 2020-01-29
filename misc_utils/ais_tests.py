import unittest

import bitstring

from pyais import message


class TestMessageMethods(unittest.TestCase):

    def test_decode_NRZI(self):
        nrzi = bitstring.Bits('0b001100110011')
        
        self.assertEqual(message.decode_NRZI(nrzi), [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1]) 
        
        self.assertEqual(message.decode_NRZI(nrzi, False), [1, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1]) 
        
    def test_bit_destuff(self):
        bits = bitstring.BitArray('0b1111101111101')
        
        self.assertEqual(message.bit_destuff(bits), bitstring.Bits('0b11111111111'))
        
    def test_to_nmea(self):
        # from http://www.bosunsmate.org/ais/
        trial = bitstring.BitArray("0b0000010001001011010101110111000010100100000000000000000000001101110010001101111000011010000111000111011100100111111010111100001101010101110100000000000010000110000110111011110111000011")
        self.assertEqual(message.to_nmea(trial), '!AIVDM,1,1,,A,14eGL:@000o8oQ`LMjOchmG@08HK,0*40')
        
    def test_ascii6_to8(self):
        
        self.assertEqual(message.ascii6_to8(bitstring.BitArray('0b000001')), "1")
        self.assertEqual(message.ascii6_to8(bitstring.BitArray('0b011010')), "J")
        self.assertEqual(message.ascii6_to8(bitstring.BitArray('0b110111')), "o")
        self.assertEqual(message.ascii6_to8(bitstring.BitArray('0b111111')), "w")
        self.assertEqual(message.ascii6_to8(bitstring.BitArray('0b011100')), "L")
        
    def test_nmea_checksum(self):
        # from http://www.bosunsmate.org/ais/
        nmea = "!AIVDM,1,1,,A,14eGL:@000o8oQ`LMjOchmG@08HK,0*"
        self.assertEqual(message.nmea_checksum(nmea), "40")
        
    def test_check_ais_crc(self):
        # from http://www.bosunsmate.org/ais/
        trial = bitstring.BitArray("0b0000010001001011010101110111000010100100000000000000000000001101110010001101111000011010000111000111011100100111111010111100001101010101110100000000000010000110000110111011110111000011")
        self.assertTrue(message.check_ais_crc(trial))
        
    def test_ais_length(self):
        pass
        
    def test_lsb_msb(self):
        self.assertEqual(message.lsb_msb(bitstring.BitArray('0b00011000')), '0b00011000') 
        self.assertEqual(message.lsb_msb(bitstring.BitArray('0b00000001')), '0b10000000')
        self.assertEqual(message.lsb_msb(bitstring.BitArray('0b0000000110000000')), '0b1000000000000001') 
        
        
if __name__ == '__main__':
    unittest.main()
    