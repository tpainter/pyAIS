
# make sure that division is floating point
from __future__ import division

import pylab as plt
from rtlsdr import *
import cmath

sdr = RtlSdr()

# configure device
sdr.sample_rate = 2.4e6
#sdr.center_freq = 162.0e6
sdr.center_freq = 93.0e6
sdr.gain = 40
sdr.freq_correction = 51

#Shift frequencies down by
freq_shift = -.3e6 #hz

#Configure plotting
#plt.ion()
plt.xlabel('Frequency (MHz)')
plt.ylabel('Relative power (dB)')

running_samples = []

@limit_calls(1)
def a(sampls, rtl):     
    running_samples.extend(sampls)
running_samples = sdr.read_samples(5000)
#sdr.read_samples_async(a)

sdr.close()

shift_scale = float(freq_shift) / sdr.sample_rate * 2.
fwT0 = 2. * cmath.pi * shift_scale
sup = complex(0, fwT0)
exp_f = cmath.exp(sup) 
running_samples_shifted = [i * exp_f for i in running_samples]

# Plot 
plt.psd(running_samples, NFFT=2**8, Fs=sdr.sample_rate/1e6, Fc=0)
plt.psd(running_samples_shifted, NFFT=2**8, Fs=sdr.sample_rate/1e6, Fc=0)
plt.show()

print(shift_scale)
print(fwT0)
print(sup)
print(exp_f)
print("Length: Orig: {} Shifted: {}".format(len(running_samples), len(running_samples_shifted)))
print(running_samples[900])
print(running_samples_shifted[900])
print("Dif: {}".format(running_samples[900] - running_samples_shifted[900]))
print("Dif: {}".format(1/shift_scale * (running_samples[900] - running_samples_shifted[900])))

