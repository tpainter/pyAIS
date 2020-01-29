#
# Smallest example of trying frquency shift.
#
# make sure that division is floating point
from __future__ import division

import pylab as plt

import cmath
import time

from pyais import sampleBuffer, rtlThread, demod

# configure device
sample_rate = 1.6e6 #2.4=25% 1.6=17%
center_freq = 93.0e6
gain = 40
freq_correction = 51

async_sample_size = 1024 # 1024 is default can be as high as 2.4e6

#Shift frequencies down by
freq_shift = -.3e6 #hz
plt.ion()

running_samples = sampleBuffer.SampleBuffer()
t_rtl = rtlThread.RtlThread(sample_rate, center_freq, gain, freq_correction, running_samples)


print(running_samples)
exit()
t_demod = demod.Demod(sample_rate, center_freq, running_samples)


"""
a = []
for _ in range(30):
    i = running_samples.retrieve()
    if i is not None:
        a.extend(i)
        plt.psd(a, NFFT=1024*8, Fs=sample_rate/1e6, Fc=0)
        plt.pause(0.0001)
        plt.plot()
        
    else:
        time.sleep(0.1)
"""
for i in range(10):
    print("Minute: {}".format(i))
    time.sleep(60)

t_rtl.stop()
exit()

