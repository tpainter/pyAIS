#
# Smallest example of trying frquency shift.
#
# make sure that division is floating point
from __future__ import division

from rtlsdr import RtlSdr

import pylab as plt
import numpy as np

import cmath
import time

sdr = RtlSdr()

# configure device
sdr.sample_rate = 1.6e6  # Hz
sdr.center_freq = 106.9e6     # Hz
sdr.freq_correction = 60   # PPM
sdr.gain = 'auto' #15.7

sdr.read_samples(1024000)

print(sdr.read_samples(512))
print("Max: {}".format(max(sdr.read_samples(5120000))))
print("Min: {}".format(min(sdr.read_samples(5120000))))

local_file = []
local_file.append("_LA_LB_Snippet16_Proc.wav") #72

exit()

for f in local_file:
    x = np.fromfile(f, np.uint8) - np.float32(127.5)
    raw_audio = 8e-3*x.view(np.complex64)
    
    i = 1024
    print(raw_audio[1024])
    print("Max: {}".format(max(raw_audio[1:i+1024])))
    print("Min: {}".format(min(raw_audio[1:i+1024])))
    
for f in local_file:
    x = np.fromfile(f, np.uint8)
    #print("one: {}".format(x[12: 14]))
    iq = x.astype(np.float64).view(np.complex128)
    #print("one: {}".format(x[12: 14]))
    iq /= 127.5
    iq -= (1+ 1j)
    raw_audio = iq
    
    
    i = 1024
    print(raw_audio[1024])
    print("Max: {}".format(max(raw_audio[1:i+1024])))
    print("Min: {}".format(min(raw_audio[1:i+1024])))

exit()

