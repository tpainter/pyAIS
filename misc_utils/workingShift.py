#
# Smallest example of trying frquency shift.
#
# make sure that division is floating point
from __future__ import division

import sys
import struct
import pylab as plt
from rtlsdr import *
import cmath
import numpy as np
from scipy import signal



running_samples = []

LOCAL = True


def ConvertData(tmp,blkSize):
    # Unpack the bytes of the string in data into unsigned characters
    readFormat = str(blkSize) + 'B'
    tmp = struct.unpack(readFormat,tmp);
    # Convert to a numpy array of floats
    tmp = np.asarray(tmp,dtype=np.float32);
    # Subtract 127 from the data (to convert to signed)
    tmp = tmp - 127;
    #convert to decimal
    tmp = tmp / 128.0
    data = np.zeros(len(tmp)//2, dtype=np.complex64);
    data.real = tmp[::2];
    data.imag = tmp[1::2];
    return data



if LOCAL:
        
    fid = open('./ReferenceData/_LA_LB_Snippet16_Proc.wav','rb')
    #fid = open('./ReferenceData/gnuais-stereo-2rx.raw','rb')
    blkSize = 1024*1000
    data = fid.read(blkSize)
    
    while len(data) >= 1:
        data = ConvertData(data,len(data))
        #print(data)
        #sys.exit()
        running_samples.extend(data)
        data = fid.read(blkSize)
    #print(running_samples[12])
    #sys.exit()
    
    #Shift frequencies by (up or down)
    freq_shift = -.125e6 #hz
    #sample_rate = 2.4e6
    sample_rate = 2.4e6
    
    #just look at a certain number of samples
    samp_start = int(1000)
    samp_end = int(5e3)
    #running_samples = running_samples[samp_start: samp_end]
    
    squelch_value = .5 ** 2
    running_samples_squelched = []
    
    for n in running_samples:
        p = n.real ** 2 + n.imag ** 2
        #print(p)
        if p > squelch_value:
            running_samples_squelched.append(n)
        else:
            running_samples_squelched.append(np.complex64(0))
    
    #print("Original: {} Sq: {}".format(len(running_samples), len(running_samples_squelched)))
    #running_samples = running_samples_squelched
    
    
    #print(running_samples[0])
    #print(type(running_samples[0]))
    #print(type(running_samples_squelched[0]))
    
else:
    sdr = RtlSdr()

    # configure device
    sdr.sample_rate = 2.4e6
    #sdr.center_freq = 162.0e6
    sdr.center_freq = 89.9e6
    #sdr.center_freq = 892.6e6
    sdr.gain = 40
    sdr.freq_correction = 51

    #Shift frequencies by (up or down)
    freq_shift = -.0e6 #hz

    running_samples = np.array(sdr.read_samples(2**16)).astype("complex64")
    print(running_samples)
    sys.exit()

    i = 5
    for _ in range(i):
        b = np.array(sdr.read_samples(2**16)).astype("complex64")
        running_samples = np.concatenate((running_samples, b))

    sdr.close()

#Shift frequency
fc1 = np.exp(1.0j*2.0*np.pi* freq_shift/sample_rate*np.arange(len(running_samples)))
running_samples_shifted = running_samples * fc1

#Filter
numtaps = 500
f = .001
upsamp = 1
decimate = 1
filter_coefs = signal.firwin(numtaps, f)
#filter_coefs = signal.gaussian(101, std=12)
running_samples_filtered = signal.upfirdn(filter_coefs, running_samples_shifted, upsamp, decimate )
#running_samples_filtered = signal.decimate(running_samples_filtered, decimate)

#print("samples: {} filtered: {}".format(len(running_samples_shifted), len(running_samples_filtered)))


#Configure plotting
plt.xlabel('Frequency (MHz)')
plt.ylabel('Relative power (dB)')
plt.subplot(4, 1, 1)
plt.psd(running_samples, NFFT=2**8, Fs=sample_rate/1e6, Fc=0)
#plt.specgram(running_samples, NFFT=2**8, Fs=sdr.sample_rate/1e6, Fc=0)
plt.subplot(4, 1, 2)
plt.psd(running_samples_shifted, NFFT=2**8, Fs=sample_rate/1e6, Fc=0)
#plt.specgram(running_samples_shifted, NFFT=2**8, Fs=sdr.sample_rate/1e6, Fc=0)
plt.subplot(4, 1, 3)
plt.psd(running_samples_filtered, NFFT=2**8, Fs=sample_rate/1e6/(decimate/2), Fc=0)
#plt.ylim([-50,-10])
plt.subplot(4, 1, 4)
plt.specgram(running_samples_filtered, Fs=sample_rate/1e6/(decimate/2)  )
plt.show()


a = running_samples_filtered
plt.scatter(a.real,a.imag)
plt.show()


