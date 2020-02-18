
from multiprocessing import Process
import time

import numpy as np


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
            self.sdr_out_A.send(samples * self.fc1_A)
            self.sdr_out_B.send(samples * self.fc1_B)   
        else:
            pad = np.zeros(self.async_sample_size - len(samples))
            samples_padded = np.append(samples, pad)
            print("Samples padded: {}".format(len(pad)))
            
            self.sdr_out_A.send(samples_padded * self.fc1_A)
            self.sdr_out_B.send(samples_padded * self.fc1_B) 
        
    def run(self):
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
        
            
        print("Radio closing...")
