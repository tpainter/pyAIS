
from multiprocessing import Process
import time

import numpy as np
import scipy.signal


class RtlReceiver(Process):
    """Set up and receive data from RTLSDR.
    """
    
    def __init__(self, sample_rate, center_freq, gain, ppm, sdr_out_A, sdr_out_B, decimate, satellite = False): 
        super(RtlReceiver, self).__init__()
                
        self.sample_rate = sample_rate
        self.center_freq = center_freq
        self.gain = gain
        self.freq_correction = ppm
        self.async_sample_size = 1024 #default 
        self.sdr_out_A = sdr_out_A
        self.sdr_out_B = sdr_out_B
        self.decimate = decimate
        
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
        
        #Create initial filter properties
        # Marine channels are 25khz wide
        self.filter_type = 'gaussian'
        
        if self.filter_type == 'gaussian':
            cut_freq = 25000 / 2.0 * 1.7 
            N = 50 
            sigma = sample_rate / (2 * np.pi * cut_freq)
            
            self.a = 1
            self.b = scipy.signal.firwin(N, cut_freq, window = ('gaussian', sigma), pass_zero = True, nyq = sample_rate / 2)
            
        elif self.filter_type == 'remez':
            cut_freq = 25 * 1000
            N = 250            
            self.a = 1
            self.b = scipy.signal.remez(N, [0, cut_freq, cut_freq + 200, 0.5*sample_rate], [1, 0],  fs = sample_rate)
            
        elif self.filter_type == 'kaiser':
            cut_freq = 25000 / 2.0 * 1.4 
            N = 100 
            beta = 9 
            self.a = 1.0
            self.b = scipy.signal.firwin(N, cut_freq, window=('kaiser', beta), nyq = sample_rate / 2)
            
        else:
            cut_freq = 25 * 1000 
            FC = cut_freq / (sample_rate / 2)
            N = 13
            self.b, self.a = scipy.signal.butter(N, FC, btype = 'lowpass', analog = False)
        
        
        #Calculate initial filter values
        self.a_A = self.a
        self.b_A = self.b
        self.a_B = self.a
        self.b_B = self.b
        
        self.zi_A = scipy.signal.lfilter_zi(self.b_A, self.a_A)
        self.zi_B = scipy.signal.lfilter_zi(self.b_B, self.a_B)
        
        
        
    def send_samples(self, samples, rtl):
        #shift frequency, filter, detect phase, and send        
        
        if len(samples) == self.async_sample_size: 
            pass
        else:
            pad = np.zeros(self.async_sample_size - len(samples))
            samples = np.append(samples, pad)
            print("Samples padded: {}".format(len(pad))) 
            
        #Frequency shift
        shifted_A = samples * self.fc1_A
        shifted_B = samples * self.fc1_B
        
        #Filter
        filtered_A, self.zi_A = scipy.signal.lfilter(self.b_A, self.a_A, shifted_A, zi = self.zi_A) 
        filtered_B, self.zi_B = scipy.signal.lfilter(self.b_B, self.a_B, shifted_B, zi = self.zi_B) 
        
        #Decmiate
        filtered_A = filtered_A[::self.decimate]
        filtered_B = filtered_B[::self.decimate]
        
        inst_phase_A = np.unwrap(np.angle(filtered_A))#inst phase
        inst_freq_A = np.diff(inst_phase_A)/(2*np.pi)*self.sample_rate #inst frequency
        inst_phase_B = np.unwrap(np.angle(filtered_B))#inst phase
        inst_freq_B = np.diff(inst_phase_B)/(2*np.pi)*self.sample_rate #inst frequency
        
        
        #Remove mean
        mean_A = inst_freq_A - np.mean(inst_freq_A)
        mean_B = inst_freq_B - np.mean(inst_freq_B)
        
        self.sdr_out_A.send(mean_A)
        self.sdr_out_B.send(mean_B) 
        
    def run(self):
        #Import here so that a working RtlSdr isn't required to work with recordings
        from rtlsdr import RtlSdr, RtlSdrTcpClient
        
        self.sdr = RtlSdr()
        #self.sdr = RtlSdrTcpClient(hostname='192.168.0.6', port=1234)
        
        # configure device
        self.sdr.center_freq = self.center_freq
        self.sdr.sample_rate = self.sample_rate        
        self.sdr.gain = self.gain
        if self.freq_correction != 0:
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
