from collections import deque
from multiprocessing import Process
import time
import sys
import wave
import math

from rtlsdr import RtlSdr, RtlSdrTcpClient
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
    1. Filter
    2. Downsample (decimate)
    3. PLL
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

        self.display_loop = 0 #Only used to limit the number of times that a matlibplot is displayed
        
        #Create filter properties
        self.filter_type = 'gaussian'
        
        if self.filter_type == 'gaussian':
            cut_freq = 9.6 / 2 * 1.5 * 1000 
            N = 33 #1201
            #sigma = sample_rate / (2 * np.pi * cut_freq)
            sigma = np.sqrt(np.log(2)) / (2 * np.pi * cut_freq) 
            
            self.a = 1
            self.b = scipy.signal.firwin(N, cut_freq, window = ('gaussian', sigma), pass_zero = True, nyq = sample_rate / 2)
            
        elif self.filter_type == 'remez':
            cut_freq = 10 * 1000
            N = 250
            
            self.a = 1
            self.b = scipy.signal.remez(N, [0, cut_freq, cut_freq + 200, 0.5*sample_rate], [1, 0],  fs = sample_rate)
            
        else:
            cut_freq = 9 * 1000 
            #LA_LB 81 w/10 82 w/9 64 w/8 61 w/8.5 81 w/8.9 64 w/9.2 61 w/9.6
            #Helsinki 0 w/9 0 w/20
            #5/4/19 36 w/20 37 w/9 37 w/8
            FC = cut_freq / (sample_rate / 2)
            N = 13
            # 82 w/13 59 w/20 0 w/51 74 w/5 57 w/14 60w/12 74w/1 72w/2
            self.b, self.a = scipy.signal.butter(N, FC, btype = 'lowpass', analog = False)
            
        #Uncomment to display filter graph
        '''
        w, h = scipy.signal.freqz(self.b)
        plt.plot(w, 20 * np.log10(abs(h)), 'b')
        plt.show()
        sys.exit()
        '''
        
        #Calculate initial filter values
        self.zi = scipy.signal.lfilter_zi(self.b, self.a)
        
        self.samples = np.zeros(1024, dtype=np.complex64)
        self.samples_A = []
        self.samples_A_filtered = deque()
        
        self.samples_plot = np.zeros(1)
        
        ais_baud = 9600
        samp_per_syb = sample_rate // self.decimate // ais_baud
        print("Samples per symbol: {}".format(samp_per_syb))
        self.stream_A = PLL(self.channel, self.samples_A_filtered, samp_per_syb, self.send_q)
        
        
        #Create a filter for the demodulated signal
        baud = 9600
        cut_freq = baud * 2
        fs = sample_rate
        N = 3
        self.pb, self.pa = scipy.signal.butter(N, cut_freq, btype = 'lowpass', analog = False, fs = fs)
        #Calculate initial filter values
        self.pzi = scipy.signal.lfilter_zi(self.pb, self.pa)
        

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
                p_filtered, self.pzi = scipy.signal.lfilter(self.pb, self.pa, np.diff(p), zi = self.pzi)                 
                '''
                plt.subplot(3, 1, 1)
                plt.scatter(np.real(self.samples), np.imag(self.samples))
                plt.subplot(3, 1, 2)
                plt.plot(np.abs(self.samples_A_filtered[0])**2)
                plt.subplot(3, 1, 3)
                plt.plot(self.sample_rate * np.diff(np.angle(self.samples_A_filtered[0])))
                #plt.pause(0.05)
                #plt.show()
                plt.clf()
                '''
                
            
            
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
        
        self.small_step = 2 #0:44 1:84 2:87 3:83 4:76 5:82 6:60 7:53 8:38 9:49 10:59 11:39 12:25
        self.step = 10
        self.max = self.step * sps
        self.mid = self.max / 2
        self.offset = 0
        
        self.prev = 0
        self.current = 0
        
        self.debug_last_phase = 0
        
        self.run_flag = True    

        self.last_samples = deque(maxlen=self.samp_sym // 2 )
        #print("Max historical length: {}".format(self.samp_sym //2 ))
        
        #self.last_samples = deque(maxlen=self.samp_sym)
        self.averages = []
        
        #Create a filter for the demodulated signal
        baud = 9600
        cut_freq = baud * 0.25
        fs = sps * baud
        N = 3
        self.pb, self.pa = scipy.signal.butter(N, cut_freq, btype = 'lowpass', analog = False, fs = fs)
        #Calculate initial filter values
        self.pzi = scipy.signal.lfilter_zi(self.pb, self.pa)
        
    def pll_testing(self):
        try:
            out = bitstring.BitArray()
            while self.run_flag:
                chunk = self.sample_queue.popleft()
                # Convert to phase
                p = np.angle(chunk)
                
                if self.channel == 'A':
                    plt.subplot(3, 1, 1)
                    plt.specgram(chunk, NFFT=512, Fs = 9600 )
                    plt.subplot(3, 1, 2)                    
                    plt.plot(np.angle(chunk))
                    plt.subplot(3, 1, 3)
                    c_filtered, self.pzi = scipy.signal.lfilter(self.pb, self.pa, chunk, zi = self.pzi)
                    plt.specgram(c_filtered, NFFT=512, Fs = 9600 )
                    plt.pause(0.05)
                    #plt.show()
                    plt.clf()
                    self.averages = []
                
                
                for s in p:
                    phase = s
                    self.last_samples.append(phase)
                    #Instead of current value, use average of last values
                    avg = np.average(self.last_samples)
                    self.averages.append(avg)
                    if avg > 0:
                        self.current = 1
                    else:
                        self.current = 0
                    
                    
                    self.offset += self.step
                    
                    if (self.prev ^ self.current) == 1:
                        #Phase change                        
                        if self.offset > self.mid:
                            self.offset -= self.small_step
                        elif self.offset < self.mid:
                            self.offset += self.small_step
                        else:
                            pass                            
                        
                        
                    if self.offset >= self.max:                         
                        if avg > 0:
                            out.append('0b1')
                        else:
                            out.append('0b0')
                        
                        self.offset -= self.max
                            
                    self.prev = self.current
                
                if out:
                    self.out_queue.send(out)
                    out.clear()
            print("PLL stopping...")
        except IndexError:
            #empty dequeue
            pass
        
        except Exception as e:
            #Other exceptions
            print(str(e))
            pass
        
    def pll(self):
        try:
            out = bitstring.BitArray()
            while self.run_flag:
                chunk = self.sample_queue.popleft()
                # Convert to phase
                p = np.angle(chunk)
                #p_filtered, self.pzi = scipy.signal.lfilter(self.pb, self.pa, p, zi = self.pzi) 
                if self.channel == 'x':
                    plt.subplot(3, 1, 1)
                    plt.scatter(np.real(chunk), np.imag(chunk))
                    plt.subplot(3, 1, 2)
                    plt.plot(np.angle(chunk))
                    plt.subplot(3, 1, 3)
                    plt.plot(self.averages)
                    #plt.pause(0.05)
                    plt.show()
                    plt.clf()
                    self.averages = []
                    
                for s in p:
                    #print(s)
                    phase = s
                    
                    if phase > 0:
                        self.current = 1
                    else:
                        self.current = 0
                    
                    self.last_samples.append(self.current)
                    
                    self.offset += self.step
                    
                    if (self.prev ^ self.current) == 1:
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
                        #print("Avg: {} Cur: {}".format(avg, self.current))
                        
                        if avg > 0:
                            self.current = 1
                        else:
                            self.current = 0
                            
                        if self.current == 0:
                            out.append('0b0')
                        else:
                            out.append('0b1')
                        
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
            
   