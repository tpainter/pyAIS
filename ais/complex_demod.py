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



class ProcessSamples(Process):
    """
    Process samples from SDR.
    1. Coarse Frequency Syncronization
    2. Timing Recovery
    3. Fine Frequency Syncronization
    4. Send to receiver for AIS decode
    """
    def __init__(self, sample_rate, channel, decimate, sdr_in, send_q): 
        super(ProcessSamples, self).__init__()
        
        self.sdr_in = sdr_in
        self.send_q = send_q
        self.sample_rate = sample_rate
        self.Ts = 1 / self.sample_rate
        self.channel = channel
        self.decimate = decimate  
        
        if self.decimate == 1:
            self.decimate1 = 1
            self.decimate2 = 1
            self.b_deci = [0,0,0]
            self.a_deci = [0,0,0]
            self.zi_deci = [0,0,0]
            self.keep = [0, 0, 0,]
            
            # Simple filter for continuous decimation        
            n = 8
            #system = scipy.signal.dlti(scipy.signal.filter_design.cheby1(n, 0.05, 0.8 / self.decimate1))
            system = scipy.signal.dlti(*scipy.signal.filter_design.cheby1(n, 0.05, 0.8 / self.decimate1))
            self.b_deci[1], self.a_deci[1] = system.num, system.den
            self.b_deci[2], self.a_deci[2] = system.num, system.den
            
            #Calculate initial filter values
            self.zi_deci[1] = scipy.signal.lfilter_zi(self.b_deci[1], self.a_deci[1])
            self.zi_deci[2] = scipy.signal.lfilter_zi(self.b_deci[2], self.a_deci[2])
            
            #Samples that need to be kept between runs
            self.keep[1] = 0
            self.keep[2] = 0
        elif self.decimate == 25:
            self.decimate1 = 5
            self.decimate2 = 5
            self.b_deci = [0,0,0]
            self.a_deci = [0,0,0]
            self.zi_deci = [0,0,0]
            self.keep = [0, 0, 0,]
            
            # Simple filter for continuous decimation        
            n = 8
            #system = scipy.signal.dlti(scipy.signal.filter_design.cheby1(n, 0.05, 0.8 / self.decimate1))
            system = scipy.signal.dlti(*scipy.signal.filter_design.cheby1(n, 0.05, 0.8 / self.decimate1))
            self.b_deci[1], self.a_deci[1] = system.num, system.den
            self.b_deci[2], self.a_deci[2] = system.num, system.den
            
            #Calculate initial filter values
            self.zi_deci[1] = scipy.signal.lfilter_zi(self.b_deci[1], self.a_deci[1])
            self.zi_deci[2] = scipy.signal.lfilter_zi(self.b_deci[2], self.a_deci[2])
            
            #Samples that need to be kept between runs
            self.keep[1] = 0
            self.keep[2] = 0
        else:
            print("Unable to process decimation. Stopping...")
            sys.exit

        self.run_flag = True
        ais_baud = 9600
        
        #Keep track of frequency offset
        self.frequency_correction = 0.0
        
        # Mueller and Muller Timing Recovery
        #Modify this factor
        self.mm_factor = 0.1 #0.1 0.5best
        self.mu = 0
        self.mueller_index = 0 #skip inputs on next process chunk
        self.mueller_out = [0, 0] # output index (let first two outputs be 0)
        self.mueller_out_rail = [0, 0] # stores values, each iteration we need the previous 2 values plus current value
        
        # Costas Loop PLL
        # Fine frequency syncronization from pysdr.org
        #Modify alpha and beta
        self.pll_alpha = 0.9 #0.132 1.5best
        self.pll_beta = 0.009 # 0.009best
        self.pll_phase = 0
        self.pll_freq = 0
        
        #Create initial filter properties
        self.filter_type = 'gaussian'
        
        if self.filter_type == 'gaussian':
            cut_freq = 9600 / 2.0 * 1.2 #    0.9:184 1.0:178 1.1:179 1.2:202 1.3:171 1.4:176 1.5:154  1.6:148 1.7:128 1.8:138 1.9:123 2.0:128
            N = 15 
            sigma = self.sample_rate / self.decimate / (2 * np.pi * cut_freq)
            
            self.a = 1
            self.b = scipy.signal.firwin(N, cut_freq, window = ('gaussian', sigma), pass_zero = True, nyq = sample_rate / self.decimate / 2)
            
        elif self.filter_type == 'remez':
            cut_freq = 9600 / 2.0 * 1.2
            N = 250
            
            self.a = 1
            self.b = scipy.signal.remez(N, [0, cut_freq, cut_freq + 200, 0.5*sample_rate / self.decimate], [1, 0],  fs = sample_rate / self.decimate)
            
        elif self.filter_type == 'kaiser':
            #Before fiddling: 1.4, 300, 8
            cut_freq = 9600 / 2.0 * 1.2 # 1.0:68 1.1:89 1.2:91 1.3:93 1.4:98 1.5:93  1.6:96
            N = 100 # 5:90 50:90 75:91 100:96 150:96 200:95 250:94 300: 400: 500:
            beta = 9 #Beta for kaiser window 1:91 5:94 7:96 8:96 9:98 10:95 14:94
            self.a = 1.0
            self.b = scipy.signal.firwin(N, cut_freq, window=('kaiser', beta), nyq = sample_rate / self.decimate / 2)
            
        elif self.filter_type == 'gnuais':
            #filter coefficients from gnuais project
            self.a = 1
            self.b = (  2.5959e-55, 2.9479e-49, 1.4741e-43, 3.2462e-38, 3.1480e-33,
                        1.3443e-28, 2.5280e-24, 2.0934e-20, 7.6339e-17, 1.2259e-13,
                        8.6690e-11, 2.6996e-08, 3.7020e-06, 2.2355e-04, 5.9448e-03,
                        6.9616e-02, 3.5899e-01, 8.1522e-01, 8.1522e-01, 3.5899e-01,
                        6.9616e-02, 5.9448e-03, 2.2355e-04, 3.7020e-06, 2.6996e-08,
                        8.6690e-11, 1.2259e-13, 7.6339e-17, 2.0934e-20, 2.5280e-24,
                        1.3443e-28, 3.1480e-33, 3.2462e-38, 1.4741e-43, 2.9479e-49,
                        2.5959e-55,)
            
        else:
            cut_freq = 9600 / 2.0 * 1.2 
            #LA_LB 81 w/10 82 w/9 64 w/8 61 w/8.5 81 w/8.9 64 w/9.2 61 w/9.6
            #Helsinki 0 w/9 0 w/20
            #5/4/19 36 w/20 37 w/9 37 w/8
            FC = cut_freq / (sample_rate / self.decimate / 2)
            N = 31
            # 82 w/13 59 w/20 0 w/51 74 w/5 57 w/14 60w/12 74w/1 72w/2
            self.b, self.a = scipy.signal.butter(N, FC, btype = 'lowpass', analog = False)
            
        
        
        
        #Calculate initial filter values
        self.zi = scipy.signal.lfilter_zi(self.b, self.a)
        
        self.samp_per_syb = int(sample_rate // self.decimate // ais_baud)
        print("Samples per symbol: {}".format(self.samp_per_syb))        
        
        
############################################################################################

    def decimate_cont(self, samples, deci_num, run_num):
        """
        Modification to the scipy decimate function that doesn't introduce artifacts at chunk boundaries.
        """
        
        #Adjust starting sample to include based on where previous runs ended
        if self.keep[run_num] == 0:
            pass
        else:
            samples = samples[deci_num - self.keep[run_num]:]
        
        #Filter before decimating
        samples_filtered, self.zi_deci[run_num] = scipy.signal.lfilter(self.b_deci[run_num], self.a_deci[run_num], samples, zi = self.zi_deci[run_num])
        
        #Figure out number of samples at end that are cut off
        n = len(samples) % deci_num
        self.keep[run_num] = n
        
        return samples_filtered[::deci_num]
        
        
    
############################################################################################
    
    def mueller(self, samples):
        # Mueller and Muller timing recovery
        # from https://www.pysdr.org
        
        N = len(samples)
        
        while self.mueller_index < N:
            self.mueller_out.append(samples[self.mueller_index + int(self.mu)]) # grab what we think is the "best" sample            
            self.mueller_out_rail.append(int(np.real(self.mueller_out[-1]) > 0) + 1j*int(np.imag(self.mueller_out[-1]) > 0))
            x = (self.mueller_out_rail[-1] - self.mueller_out_rail[-3]) * np.conj(self.mueller_out[-2])
            y = (self.mueller_out[-1] - self.mueller_out[-3]) * np.conj(self.mueller_out_rail[-2])
            mm_val = np.real(y - x)
            self.mu += self.samp_per_syb + self.mm_factor*mm_val            
            self.mueller_index += int(np.floor(self.mu)) # round down to nearest int since we are using it as an index
            self.mu = self.mu - np.floor(self.mu) # remove the integer part of mu
            
        self.mueller_index = self.mueller_index - N #skip the proper number of inputs next time
        out = self.mueller_out[2:] # the first two samples are duplicates from the last run
        self.mueller_out = self.mueller_out[-2:] # keep last two values to start next processing of samples
        self.mueller_out_rail = self.mueller_out_rail[-2:] # keep last two values to start next processing of samples
        return out

##################################################################################################

    def costas(self, symbol_samples): 
        # PLL via costas loop
        # from https://www.pysdr.org
        
        out = bitstring.BitArray()
        temp = []
            
        for s in symbol_samples:
            s_prime = s * np.exp(-1j*self.pll_phase) # adjust the input sample by the inverse of the estimated phase offset
            error = np.real(s_prime) * np.imag(s_prime) # This is the error formula for 2nd order Costas Loop (e.g. for BPSK)
            temp.append(s_prime)
            
            # Advance the loop (recalc phase and freq offset)
            self.pll_freq += (self.pll_beta * error)
            self.pll_phase += self.pll_freq + (self.pll_alpha * error)

            # Adjust phase so its always between 0 and 2pi
            while self.pll_phase >= 2*np.pi:
                self.pll_phase -= 2*np.pi
            while self.pll_phase < 0:
                self.pll_phase += 2*np.pi
            
            bit = np.real(s_prime)
            
            if bit > 0:
                out.append('0b1')
            else:
                out.append('0b0')
        
        
        if False and self.channel == 'A':
            plt.scatter(np.real(temp), np.imag(temp))
            plt.xlim(-1, 1)
            plt.ylim(-1, 1)
            #plt.plot(temp)
            #plt.plot(out)
            plt.pause(0.05)
            #plt.show()
            plt.clf()
                
        return out
  
#################################################################################################  
    def run(self):
        print("Starting filtering...")
        while self.run_flag:
            try:
                #will block until there is something to receive
                r = self.sdr_in.recv()
                self.samples = r
            except EOFError:
                #pipe was closed
                self.run_flag = False  
                self.stream_A.run_flag = False
                #self.send_q.send("PIPE_END_FLAG")
                continue
            except Exception as e:
                #any other error is unexpected
                print("Pipe error...")
                print(str(e))
                time.sleep(1)
                continue
            
                        
            #Apply frequency correction
            t = np.arange(0, self.Ts*len(self.samples), self.Ts)            
            self.samples = self.samples * np.exp(-1j*2*np.pi*self.frequency_correction*t/2.0)
            
            #Do coarse frequency syncronization from pysdr.org
            samples_sqr = self.samples**2
            psd = np.fft.fftshift(np.abs(np.fft.fft(samples_sqr)))
            f = np.linspace(-self.sample_rate/2.0, self.sample_rate/2.0, len(psd))            
            max_freq = f[np.argmax(psd)]  
            
            #Update frequency correction. Slowly adjust amount
            ##Seems to cause more trouble than it solves. TODO
            #self.frequency_correction += 0.1 * max_freq
            #self.frequency_correction = max_freq
            
            # TODO This is very sensitive to number of samples inspected at once.
            #print("Channel {} Frequency Offset: {}".format(self.channel, max_freq))
            
            # Decimate
            #self.samples = scipy.signal.decimate(self.samples, self.decimate, zero_phase = True)
            if self.decimate == 1:
                #pass
                #Decimate in two passes
                self.samples = self.decimate_cont(self.samples, self.decimate1, 1)
                self.samples = self.decimate_cont(self.samples, self.decimate2, 2)
            else:
                #Decimate in two passes
                self.samples = self.decimate_cont(self.samples, self.decimate1, 1)
                self.samples = self.decimate_cont(self.samples, self.decimate2, 2)
            
            # Filter
            chunk, self.zi = scipy.signal.lfilter(self.b, self.a, self.samples, zi = self.zi)
            
            # do mueller and muller
            symbol_samples = self.mueller(chunk)
            
            if False and self.channel == 'A':
                plt.scatter(np.real(symbol_samples), np.imag(symbol_samples))
                plt.pause(0.05)
                #plt.show()
                plt.clf()
            
            
            # do fine frequency sync and pll
            self.send_q.send(self.costas(symbol_samples))       
            
            
            
        print("Stopping filtering ...")
        
        

