
from multiprocessing import Process
import time
import wave

import numpy as np


class FromFile(Process):
    """Set up and receive data from RTLSDR.
    """
    
    def __init__(self, sample_rate, center_freq, sdr_out_A, sdr_out_B, local_file = None, satellite = False): 
        super(FromFile, self).__init__()
        
        self.sample_rate = sample_rate
        self.center_freq = center_freq
        self.async_sample_size = 1024 * 16
        self.sdr_out_A = sdr_out_A
        self.sdr_out_B = sdr_out_B
        self.local_file = local_file
        self.channels = 1
        
        if satellite:
            # Channel 75
            self.freq_shift_A = self.center_freq - 156.775 * 1e6
            # Channel 76
            self.freq_shift_B = self.center_freq - 156.825 * 1e6
        else:
            # Channel 88B
            self.freq_shift_A = self.center_freq - 162.025 * 1e6
            # Channel 87B
            self.freq_shift_B = self.center_freq - 161.975 * 1e6
        
        print("Frequency shift A: {}MHz".format(self.freq_shift_A / 1e6))
        print("Frequency shift B: {}MHz".format(self.freq_shift_B / 1e6))
        
        self.fc1_A = np.exp(1.0j*2.0*np.pi* self.freq_shift_A/self.sample_rate*np.arange(self.async_sample_size))
        self.fc1_B = np.exp(1.0j*2.0*np.pi* self.freq_shift_B/self.sample_rate*np.arange(self.async_sample_size))
        
        
        
    def send_samples(self, samples):
        #Shift frequency and send
        
        if len(samples) == self.async_sample_size * self.channels:
            if self.channels == None:
                #This will shift frequency if recorded in complex-type
                self.sdr_out_A.send(samples * self.fc1_A)
                self.sdr_out_B.send(samples * self.fc1_B)
            elif self.channels == 2:
                self.sdr_out_A.send(samples[::2])
                self.sdr_out_B.send(samples[1::2])
            else:
                self.sdr_out_A.send(samples)
        
        else:
            pad = np.zeros(self.async_sample_size - len(samples)) / 2
            samples_padded = np.append(samples, pad)
            print("Samples padded: {}".format(len(pad)))
            
            if self.channels == None:
                #This will shift frequency if recorded in complex-type
                self.sdr_out_A.send(samples * self.fc1_A)
                self.sdr_out_B.send(samples * self.fc1_B)
            elif self.channels == 2:
                self.sdr_out_A.send(samples[::2])
                self.sdr_out_B.send(samples[1::2]) 
            else:
                self.sdr_out_A.send(samples_padded)
        
    def run(self):
    
        for f in self.local_file:
            #Process *.wav files seperately because they have more embeded data.
            if f[0].endswith(".wav"):
                try:
                    print("Processing *.wav file.")
                    fd = wave.open(f[0], 'rb')
                    xb = fd.readframes(fd.getnframes())
                    
                    #If there is only one channel, there is no need to keep two separate code paths.
                    channels = fd.getnchannels()
                    if channels == 1:
                        self.channels = 1
                        self.sdr_out_B.close()
                    
                    #Update sample rate based on what is encoded in file.
                    rate = fd.getframerate()
                    print("*.wav file samplerate: {}".format(rate))
                    self.sample_rate = rate
                    
                    #Check whether the sampes are one or two bytes wide.
                    bytes = fd.getsampwidth()
                    if bytes == 1:
                        x = np.fromstring(xb, np.int8)
                        print("*.wav file sample size: int8")
                    else:
                        x = np.fromstring(xb, np.int16)
                        print("*.wav file sample size: int16")
                    
                    fd.close()
                except wave.Error:
                    print("Error reading WAV file.")
                    print(e)
                
                raw_audio = x.astype(np.float64)
            
            elif f[1] == "8u":
                ### 8 bit unsigned input
                x = np.fromfile(f[0], np.uint8)
                raw_audio = x.astype(np.float64).view(np.complex128)
                raw_audio /= 127.5
                raw_audio -= (1+ 1j)
            elif f[1] == "8s":
                ### 8 bit signed input
                x = np.fromfile(f[0], np.int8)
                raw_audio = x.astype(np.float64).view(np.complex128)
            elif f[1] == "16u":
                ##16bit unsigned input                    
                x = np.fromfile(f[0], np.uint16)
                raw_audio = x.astype(np.float64).view(np.complex128)
                raw_audio /= 2**16 / 2 - 0.5
                raw_audio -= (1+1j)
            elif f[1] == "16s":    
                ##16bit signed input
                x = np.fromfile(f[0], np.int16)
                raw_audio = x.astype(np.float64).view(np.complex128)
            elif f[1] == "16d":    
                ##16bit signed input
                self.channels = 2
                x = np.fromfile(f[0], np.int16)
                #raw_audio = x.astype(np.float64).view(np.complex128)
                raw_audio = x
            else:
                print("Unsupported sample type.")
            
            
            for i in range(0, len(raw_audio), self.async_sample_size * self.channels):
                self.send_samples(raw_audio[i: i + self.async_sample_size * self.channels])
        
        print("All samples stored.")
        time.sleep(1)
        self.sdr_out_A.close()
        self.sdr_out_B.close()
            
        print("File read closing...")
