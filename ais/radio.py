from collections import deque
from multiprocessing import Process
import time
import sys
import wave
import math

import numpy as np
import scipy.signal

try:
    import pylab as plt
except:
    pass

import bitstring

class RtlReceiver(Process):
    """Set up and receive data from RTLSDR.
    """
    
    def __init__(self, sample_rate, center_freq, gain, ppm, sdr_out_A, sdr_out_B, local_file = None, satellite = False): 
        super(RtlReceiver, self).__init__()
                
        self.sample_rate = sample_rate
        self.center_freq = center_freq
        self.gain = gain
        self.freq_correction = ppm
        self.async_sample_size = 1024 #default 
        self.sdr_out_A = sdr_out_A
        self.sdr_out_B = sdr_out_B
        self.local_file = local_file        
        
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
        
        
        
    def send_samples(self, samples, rtl):
        #shift frequency and send
        #print(self.samples)
        
        if len(samples) == self.async_sample_size: 
            #Remove DC offset
            #samples = samples - np.mean(samples)
            self.sdr_out_A.send(samples * self.fc1_A)
            self.sdr_out_B.send(samples * self.fc1_B)   
        else:
            print("Samples dropped: {}".format(self.async_sample_size - len(samples)))
        
    def run(self):
        if self.local_file is None:
            #Import here so that a working RtlSdr isn't required to work with recordings
            from rtlsdr import RtlSdr, RtlSdrTcpClient
            
            self.sdr = RtlSdr()
            #self.sdr = RtlSdrTcpClient(hostname='192.168.0.6', port=1234)
            
            # configure device
            self.sdr.center_freq = self.center_freq
            self.sdr.sample_rate = self.sample_rate        
            self.sdr.gain = self.gain
            self.sdr.freq_correction = self.freq_correction
            
            #try for some extra filtering
            try:
                self.sdr.bandwidth = (.350 * 1e6)
                pass
            except IOError:
                print("No bandwidth adjustment availible.")
            
            print("SDR Frequency: {}MHz".format(self.sdr.get_center_freq() / 1e6))
            print("SDR Sample Rate: {}MS/s".format(self.sdr.get_sample_rate() / 1e6))
            
            self.sdr.read_samples_async(self.send_samples, self.async_sample_size)
        else:
            for f in self.local_file:
                if f[1] == "8u":
                    ### 8 bit unsigned input
                    if f[0].endswith(".wav"):
                        try:
                            wav = wave.open(f[0], 'rb')
                            xb = wav.readframes(wav.getnframes())
                            x = np.fromstring(xb, np.uint8)
                            wav.close()
                        except wave.Error:
                            print("Error reading WAV file.")
                            print(e)
                    else:
                        x = np.fromfile(f[0], np.uint8)
                    raw_audio = x.astype(np.float64).view(np.complex128)
                    raw_audio /= 127.5
                    raw_audio -= (1+ 1j)
                elif f[1] == "8s":
                    ### 8 bit signed input
                    if f[0].endswith(".wav"):
                        try:
                            wav = wave.open(f[0], 'rb')
                            xb = wav.readframes(wav.getnframes())
                            x = np.fromstring(xb, np.int8)
                            wav.close()
                        except wave.Error:
                            print("Error reading WAV file.")
                            print(e)
                    else:
                        x = np.fromfile(f[0], np.int8)
                    raw_audio = x.astype(np.float64).view(np.complex128)
                elif f[1] == "16u":
                    ##16bit unsigned input                    
                    x = np.fromfile(f[0], np.int16)
                    raw_audio = x.astype(np.float64).view(np.complex128)
                    raw_audio /= 2**16 / 2 - 0.5
                    raw_audio -= (1+1j)
                elif f[1] == "16s":    
                    ##16bit signed input
                    x = np.fromfile(f[0], np.int16)
                    raw_audio = x.astype(np.float64).view(np.complex128)
                else:
                    print("Unsupported sample type.")
                
                
                for i in range(0, len(raw_audio), self.async_sample_size):
                    self.send_samples(raw_audio[i: i + self.async_sample_size], None)
            
            print("All samples stored.")
            time.sleep(1)
            #self.sdr_out_A.send("PIPE_END_FLAG")
            self.sdr_out_A.close()
            #self.sdr_out_B.send("PIPE_END_FLAG")
            self.sdr_out_B.close()
            
        print("Radio closing...")
