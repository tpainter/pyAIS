import binascii
import time
import collections
from multiprocessing import Process

import bitstring


class ProcessAISBits(Process):
    """
    Takes a stream of bits (already frequency changed, filtered, etc., but before NRZI) and outputs a NMEA 
    message if found.
    
    """
    def __init__(self, ais_channel, input_bits, display_stats = 2*60):
        super(ProcessAISBits, self).__init__()
        
        self.run_flag = True
        self.channel = ais_channel
        self.input_bits = input_bits  
        
        self.receive_buffer = bitstring.BitArray()
        self.decoded_bits = bitstring.BitArray()
        self.possible_msg = []
        
        #Keep track of NRZI status so we don't lose a bit between buffer runs.
        self.last_nrzi = True
        
        self.hdlc_flag = bitstring.Bits(hex='0x7e')        
        
        #stats
        self.display_stats = display_stats
        self.stat_last = time.time()
        self.msg_decode = 0
        self.msg_invalid_crc = 0
        self.msg_invalid_length = 0
        
        
    def run(self):
        print("Starting message processing {}...".format(self.channel))
        while self.run_flag:            
            if self.input_bits.poll(1.0):                 
                #Get bits from pipe
                try:
                    r = self.input_bits.recv()
                    '''if r == "PIPE_END_FLAG":
                        print("Pipe closed.")
                        print("Messages closing...")
                        self.run_flag = False
                        break
                    '''
                    self.receive_buffer.append(r)
                except EOFError:
                    #pipe has been closed
                    print("Pipe closed.")
                    self.run_flag = False
                    continue                
                except Exception as e:
                    print(str(e))
                    self.run_flag = False
                    continue     
            else:
                pass
               
            self.decoded_bits.append(self.decode_NRZI(self.receive_buffer, self.last_nrzi))
            
            
            self.receive_buffer.clear()            
            
            #Search for start/stop flag
            previous = None
            for f in self.decoded_bits.findall(self.hdlc_flag):
                if previous is not None:
                    #Locations are at begining of flag. This copies bits without flags at ends.
                    self.possible_msg.append(self.decoded_bits[previous+8: f])
                previous = f
            
            #TODO: Does this actually keep information if message is split between decoding sessions?
            
            #Clear out bits that have been searched
            if previous is not None:
                del self.decoded_bits[:previous]
               
            #AIS message frame is 256 bits. Max message is over 5 frames. If  
            # we have more bits than this, we can discard.
            if len(self.decoded_bits) > 256 * 5:
                m = len(self.decoded_bits) / 256
                print("Culling bits ({})...".format(self.channel))
                del self.decoded_bits[:256*m]
            
            for m in self.possible_msg:
                ais_unstuff = bit_destuff(m)
                
                #Convert LSB->MSB
                ais_msb = lsb_msb(ais_unstuff)

                #check message length
                if not check_ais_length(ais_msb):
                    #print("AIS length check failled")
                    self.msg_invalid_length += 1
                    continue
                
                #check AIS crc (hdlc)
                if not check_ais_crc(ais_unstuff):
                    #print("AIS crc check failled")
                    self.msg_invalid_crc += 1
                    continue

                
                nemea_text = to_nmea(ais_msb, self.channel)
                self.msg_decode += 1
                print("NMEA Text: {}".format(nemea_text))
                
            #Clear out possible messages
            del self.possible_msg[:]
            
            #Diplay stats
            if self.display_stats is not None:
                if time.time() > self.stat_last + self.display_stats:
                    print("Channel {} Messages - Bad Length: {}, Bad CRC: {}, Good: {}".format(self.channel, self.msg_invalid_length, self.msg_invalid_crc, self.msg_decode))
                    self.stat_last = time.time()
            
            
            #Sleep before running loop again.
            time.sleep(0.001)
             
                
    def decode_NRZI(self, NRZI, start = True):
        """ Used to decode NRZI bits
        """
        
        #TODO: Make output bistring.BitArray
        
        out = [None] * len(NRZI)
        last = start
        for i in range(0, len(NRZI)):
            if NRZI[i] == last:
                #Same is "1"
                out[i] = 1
            else:
                #Different is "0"
                out[i] = 0
                last = NRZI[i]
        
        self.last_nrzi = last
        return bitstring.BitArray(out)        

            
            
            
################################################################            
            
def decode_NRZI(NRZI, start = True):
    """ Used to decode NRZI bits
    """
    
    #TODO: Make output bistring.BitArray
    
    out = [None] * len(NRZI)
    last = start
    for i in range(0, len(NRZI)):
        if NRZI[i] == last:
            #Same is "1"
            out[i] = 1
        else:
            #Different is "0"
            out[i] = 0
            last = NRZI[i]
    
    return out
  
def bit_destuff(bits):
    """ Message is subject to bit stuffing. Remove first "0" after five "1"s
    e.g. "11111001" becomes "1111101"
    """
    out = bits.copy()
    stuff = bitstring.Bits(bin='111110')
    if bits.find(stuff):
        #Keep track of number of removed bits so that index can be modified.
        popped_bits = 0
        stuffed = bits.findall(stuff)
        for s in stuffed:
            pos = s + 5 - popped_bits
            del out[pos]
            popped_bits += 1      
    #print("Bits unstuffed: {}".format(popped_bits))
    return out
        
    

def to_nmea(bits, channel = "A"):
    """Returns NMEA text.
    See: http://www.bosunsmate.org/ais/
    """
    
    bits_copy = bits[:-16] #Don't pass along crc to be encoded in NMEA
    pad = 0
    #Check that bits are divisible into 6bit characters
    if len(bits_copy) % 6 != 0:
        #Need pad bits
        pad = 6 - len(bits_copy) % 6    
        #print("Message length: {} , Need pad bits: {}".format(len(bits), pad))
    
    #Add the padding    
    for i in range(pad):
        bits_copy.append('0b0')
    
    payload = ""
    for i in range(0, len(bits_copy), 6):
        payload += ascii6_to8(bits_copy[i:i+6])
        #print("Bin: {} Symb: {}".format(bits_copy[i:i+6].bin, ascii6_to8(bits_copy[i:i+6])))
    
    #Combine into full NMEA format. All NMEA AIS position messages start the same way.
    nmea = "!AIVDM,1,1,,{},{},{}*".format(channel, payload, pad)
    #Add checksum
    nmea += nmea_checksum(nmea)
    
    return nmea
    
def ascii6_to8(bits):
    """Converts ASCII 6bit to equivelant ASCII character
    """
    
    if (len(bits) != 6):
        #Required 6bit characters
        print("6 bits not provided.")
        return
        
    value = bits.uint
    
    if value <= 39:
        return chr(value + 48)
    elif value <= 63:
        return chr(value + 56)
    else:
        #Error
        print("ascii6 encode error")
        return

 
def nmea_checksum(message):
    """Returns checksum (crc32) digits from given message.
    """    
    
    #Check that message starts with "!" and ends with "*"
    if (message[0] == "!" and message[-1] == "*"):
        #This is good
        pass
    else:
        print("Not able to get NMEA checksum")
        return
    
    crc = 0
    for i in message[1:-1]:
        crc ^= ord(i)
      
    return format(crc, '02X')
    
    
def check_ais_crc(bits):
    """Check CRC code for AIS only, not NMEA.
    "bits" should include message and checksum.
    See: https://stackoverflow.com/questions/25239423/crc-ccitt-16-bit-python-manual-calculation
    """    
    
    #Number of bits has to be multiple of 8. If not, check isn't valid and will fail.
    if len(bits) % 8 != 0:
        #print("Message bits not multiple of 8.")
        return False
    
    #Should be '0x1d0f'  https://stackoverflow.com/questions/7983862/calculating-fcscrc-for-hdlc-frame
    return (binascii.crc_hqx(bits.bytes, 0xffff) == 0x1d0f)
        

    
def lsb_msb(bits):
    """
    Convert lsb binary to msb
    """
    
    swapped = bitstring.BitArray('')
    for i in range(0, len(bits), 8):
        lsb_byte = bits[i : i +8]
        lsb_byte.reverse()
        swapped.append(lsb_byte)
    
    return swapped

# message type : fixed length (or -1 if variable)
valid_msg_lengths = collections.defaultdict(lambda : -1, {
    1 : 168,
    2 : 168,
    3 : 168,
    4 : 168,
    9 : 168,
    10 : 72,
    11 : 168,
    18 : 168,
    22 : 168,
    23 : 160,
    24 : 168,
    27 : 96, #typical, may also be 168 if not per spec
})

def check_ais_length(bits):
    """
    For a given possible message (bits), check if message type matches payload length.
    """
    length = len(bits) - 16 #take away crc checksum since it isn't part of the message
    
    #all messages are at least 96 bits long
    if length < 96:
        return False
        
    type = bits[:6].uint
    
    #give more leeway to satellite AIS
    if type == 27:
        if length <= 168:
            return True
    else:
        return (length == valid_msg_lengths[type])
    

