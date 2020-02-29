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
    1. 
    2. 
    3. 
    4. Send to receiver for AIS decode
    """
    def __init__(self, sample_rate, channel, decimate, sdr_in, send_q): 
        super(ProcessSamples, self).__init__()
        
        self.sdr_in = sdr_in
        self.send_q = send_q
        self.sample_rate = sample_rate
        self.channel = channel
        self.decimate = decimate    

        self.run_flag = True
        ais_baud = 9600
        
        #Create initial filter properties
        self.filter_type = 'kaiser'
        
        if self.filter_type == 'gaussian':
            cut_freq = 9600 / 2.0 * 1.7 #    1.0:80 1.1:87 1.2:93 1.3:92 1.4:88 1.5:92  1.6:93 1.7:95 1.8:93 1.9:89 2.0:91
            N = 50 #       10:92 33:90 40:92 50:93 75:90 100:92 200:92 300:91
            sigma = sample_rate / (2 * np.pi * cut_freq)
            
            self.a = 1
            self.b = scipy.signal.firwin(N, cut_freq, window = ('gaussian', sigma), pass_zero = True, nyq = sample_rate / 2)
            
        elif self.filter_type == 'remez':
            cut_freq = 10 * 1000
            N = 250
            
            self.a = 1
            self.b = scipy.signal.remez(N, [0, cut_freq, cut_freq + 200, 0.5*sample_rate], [1, 0],  fs = sample_rate)
            
        elif self.filter_type == 'kaiser':
            #Before fiddling: 1.4, 300, 8
            cut_freq = 9600 / 2.0 * 1.4 # 1.0:68 1.1:89 1.2:91 1.3:93 1.4:98 1.5:93  1.6:96
            N = 100 # 5:90 50:90 75:91 100:96 150:96 200:95 250:94 300: 400: 500:
            beta = 9 #Beta for kaiser window 1:91 5:94 7:96 8:96 9:98 10:95 14:94
            self.a = 1.0
            self.b = scipy.signal.firwin(N, cut_freq, window=('kaiser', beta), nyq = sample_rate / 2)
            
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
            cut_freq = 9 * 1000 
            #LA_LB 81 w/10 82 w/9 64 w/8 61 w/8.5 81 w/8.9 64 w/9.2 61 w/9.6
            #Helsinki 0 w/9 0 w/20
            #5/4/19 36 w/20 37 w/9 37 w/8
            FC = cut_freq / (sample_rate / 2)
            N = 13
            # 82 w/13 59 w/20 0 w/51 74 w/5 57 w/14 60w/12 74w/1 72w/2
            self.b, self.a = scipy.signal.butter(N, FC, btype = 'lowpass', analog = False)
        
        
        #Calculate initial filter values
        self.zi = scipy.signal.lfilter_zi(self.b, self.a)
        
        self.samples = np.zeros(1024, dtype=np.complex64)
        self.samples_A = []
        self.samples_A_filtered = deque()        
        
        samp_per_syb = int(sample_rate // self.decimate // ais_baud)
        print("Samples per symbol: {}".format(samp_per_syb))
        self.stream_A = PLL(self.channel, self.samples_A_filtered, samp_per_syb, self.send_q)
        
        

    def run(self):
        print("Starting filtering...")
        while self.run_flag:
            try:
                #will block until there is something to receive
                r = self.sdr_in.recv()
                if r == "PIPE_END_FLAG":
                    print("Got end flag demod")
                    self.run_flag = False
                    self.stream_A.run_flag = False
                    #self.send_q.send("PIPE_END_FLAG")
                    break
                else:
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
            
            #remove offset
            #self.samples = self.samples - np.mean(self.samples)
            #print(np.real(np.mean(self.samples)))
            #print(np.mean(self.samples))
            
            a_full, self.zi = scipy.signal.lfilter(self.b, self.a, self.samples, zi = self.zi)                
            
            #self.samples_A_filtered.append(self.samples)
            self.samples_A_filtered.append(scipy.signal.decimate(a_full, self.decimate, zero_phase = True))
            
            if self.channel == 'x':
                #self.samples_plot = np.append(self.samples_plot, scipy.signal.decimate(a_full, self.decimate, zero_phase = True))
                #self.samples_plot = np.append(self.samples_plot, self.samples)
                
                p = np.angle(self.samples_A_filtered[0])
                
                
                #plt.subplot(3, 1, 1)
                #plt.scatter(np.real(self.samples), np.imag(self.samples))
                #plt.scatter(range(len(self.samples)), np.imag(self.samples))
                #plt.scatter(range(len(self.samples)), np.real(self.samples))
                #plt.subplot(3, 1, 2)
                #plt.plot(np.abs(self.samples_A_filtered[0])**2)
                #plt.subplot(3, 1, 3)
                #plt.plot(self.sample_rate/np.pi/2 * np.diff(np.angle(self.samples_A_filtered[0])))
                #plt.plot(p)
                #plt.pause(0.05)
                #plt.show()
                #plt.clf()
                
                
            
            
            #PLL and send
            self.stream_A.pll()
        print("Stopping filtering ...")
        
class PLL():
    """
    Takes filtered samples from queue and performs:
    1. PLL (phase lock loop)
    """
    def __init__(self, channel, samples, sps, out):
        self.channel = channel
        self.sample_queue = samples
        self.samp_sym = sps
        self.out_queue = out        
        
        self.small_step = 3 
        self.step = 10 
        self.max = self.step * sps
        self.mid = self.max / 2
        self.offset = 0
        
        self.prev = 0
        self.current = 0
        
        self.run_flag = True    

        #self.last_samples = deque(maxlen=self.samp_sym // 2 ) #for working pll
        self.last_samples = deque(maxlen=self.samp_sym - 1) #for testing pll 5: 4:88 3:84 2:81 1:
        
        
        
        
    def pll(self): 
        try:
            out = bitstring.BitArray()
            while self.run_flag:
                chunk = self.sample_queue.popleft()
                # Convert to phase
                #p = np.angle(chunk)
                #p = np.imag(chunk)
                p = chunk
                
                #y5 = chunk[1:] * np.conj(chunk[:-1])  
                #p = np.angle(y5)/(2*np.pi)               
                #plt.plot(p)
                #plt.show()
                    
                for s in p:
                    phase = s
                    
                    if phase > 0:
                        self.current = 1
                    else:
                        self.current = 0
                    
                    self.last_samples.append(self.current)
                    
                    self.offset += self.step
                    
                    if (self.prev ^ self.current):
                        #Phase change                        
                        if self.offset > self.mid:
                            self.offset -= self.small_step
                        elif self.offset < self.mid:
                            self.offset += self.small_step
                        else:
                            pass
                            
                        
                        
                    if self.offset >= self.max:                        
                        #Instead of current value, use average of last values
                        avg = np.average(self.last_samples)
                        
                        if avg > 0.49:
                            self.current = 1
                            out.append('0b1')
                        else:
                            self.current = 0
                            out.append('0b0')
                        
                        self.offset -= self.max
                            
                    self.prev = self.current
                
                if out:
                    self.out_queue.send(out)
                    out.clear()
        
        except IndexError:
            #empty dequeue
            pass
        
        except Exception as e:
            #Other exceptions
            print(str(e))
            pass
            