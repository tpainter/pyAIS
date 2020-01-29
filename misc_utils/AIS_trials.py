import sys
import numpy as np
import pylab as plt
import scipy.signal

import bitstring

from pyais import message
from pyais import radio





# Load from sample file
#raw_audio = np.fromfile("2015-04-19-test-161975000-p45-s48k.raw", np.int16)

x = np.fromfile("2015-04-19-test-161975000-p45-s48k.raw", np.uint8) - np.float32(127.5)
#x = np.fromfile("_LA_LB_Snippet16_Proc.wav", np.uint8) - np.float32(127.5)
#x = np.fromfile("2015-04-19-test-162025000-p45-s48k.raw", np.uint8) - np.float32(127.5)
raw_audio = 8e-3*x.view(np.complex64)

sample_rate = 48000
ais_baud = 9600
samples_per_bit = sample_rate // ais_baud
squelch = 0.5

##Shift signal frequency
#Shift frequencies by (up or down)
freq_shift = -.0 * 1e6 #hz
fc1 = np.exp(1.0j*2.0*np.pi* freq_shift/sample_rate*np.arange(len(raw_audio)))
raw_audio = raw_audio * fc1



print("Max seconds: {}".format(len(raw_audio) / sample_rate))

#First Signal
#running_samples = raw_audio[int(sample_rate * 1.74) : int(sample_rate * 1.765)]
#Second Signal
#running_samples = raw_audio[int(sample_rate * 15.16) : int(sample_rate * 15.21)]
#Third Signal
#running_samples = raw_audio[int(sample_rate * 34.38) : int(sample_rate * 34.42)]
#Fourth Signal
#running_samples = raw_audio[int(sample_rate * 81.74) : int(sample_rate * 81.77)]
#Testing Signal
#running_samples = raw_audio[int(sample_rate * 1.73 ) : int(sample_rate * 1.8)]
#running_samples = raw_audio[:int(sample_rate * 10)]
#running_samples = raw_audio[:len(raw_audio)//2]
running_samples = raw_audio[int(sample_rate * 1.74) : int(sample_rate * 1.765)]

b = radio.matlab_style_gauss2D()
a = [1.0]
running_samples_filtered = scipy.signal.filtfilt(b[0], a, running_samples)

y = running_samples[1:] * np.conj(running_samples[:-1])
z = np.angle(y)

print("x: {}, y: {}, z: {}".format(len(running_samples), len(y), len(z)))

plt.plot(np.angle(running_samples)/np.max(np.angle(running_samples)))
plt.show()

#b = radio.matlab_style_gauss2D()
#a = [1.0]
#running_samples_filtered = signal.filtfilt(b[0], a, running_samples)
#Filter seems to greatly decrease received messages
#gaussian = signal.gaussian(100, 1 ,True)
#gaussian /= gaussian.sum()
#running_samples_filtered = np.convolve(running_samples, gaussian, 'same')

running_samples_filtered = running_samples

b =  scipy.signal.firwin(17, 9600, width=None, window=('gaussian', 3.0), pass_zero=True, scale=True, nyq=None, fs=48000/2)
#running_samples_filtered = scipy.signal.filtfilt(b, 1.0, running_samples, axis=-1, padtype='odd', padlen=None, method='pad', irlen=None)

#running_samples_filtered = scipy.signal.resample_poly(running_samples, 1, 1, axis=0, window=('gaussian', 3))

#print("Sample mean: {}".format(np.abs(np.mean(running_samples_filtered))))
#squelch based on sample power
#running_samples_filtered[np.abs(running_samples_filtered) < squelch ] = 0
#running_samples_filtered = radio.squelch(running_samples_filtered, squelch)

#Configure plotting
plt.close('all')
plt.figure(figsize=(13, 8))
'''
plt.xlabel('Frequency (MHz)')
plt.ylabel('Relative power (dB)')
plt.subplot(6, 1, 1)
plt.psd(running_samples, NFFT=2**8, Fs=sample_rate/1e6, Fc=162.975/1e6)

x = running_samples
fs = sample_rate
f, t, Sxx = signal.spectrogram(x, fs, return_onesided = False)
plt.subplot(6, 1, 2)
plt.pcolormesh(t, f, Sxx)
plt.ylabel('Frequency [Hz]')
plt.xlabel('Time [sec]')

plt.subplot(6, 1, 3)
plt.plot(np.angle(running_samples))
plt.ylabel('Phase')
plt.xlabel('Time [sec]')
'''
'''
plt.xlabel('Frequency (MHz)')
plt.ylabel('Relative power (dB)')
plt.subplot(4, 1, 1)
 
plt.psd(running_samples_filtered, NFFT=2**8, Fs=sample_rate/1e6, Fc=162.975/1e6)


x = running_samples_filtered
fs = sample_rate
f, t, Sxx = signal.spectrogram(x, fs, return_onesided = False)
plt.subplot(4, 1, 2)
plt.pcolormesh(t, f, Sxx)
plt.ylabel('Frequency [Hz]')
plt.xlabel('Time [sec]')

plt.subplot(4, 1, 3)
plt.plot(np.angle(running_samples_filtered))
plt.ylabel('Phase')
plt.xlabel('Sample')

plt.subplot(4, 1, 4)
plt.plot(np.abs(running_samples_filtered))
plt.ylabel('Amplitude')
plt.xlabel('Samples')

plt.show()
'''




###PATH  using bitstring

#squelched_samples = radio.squelch(running_samples_filtered, squelch)
NRZI_bits = radio.pll(running_samples_filtered, samples_per_bit)

decoded_bits = bitstring.BitArray(message.decode_NRZI(NRZI_bits, True))
hdlc_flag = bitstring.Bits(hex='0x7e')

possible_msg = []
flags = decoded_bits.findall(hdlc_flag)
i = 0
prev = None
for f in flags:
    if prev is not None:
        aismsg = bitstring.BitArray()
        aismsg = decoded_bits[prev+8:f]
        possible_msg.append(aismsg)
        i += 1
    prev = f
print("Possible messages: {}".format(i))
    
for m in possible_msg:
    ais_unstuff = message.bit_destuff(m)

    #check AIS crc (hdlc)
    if not message.check_ais_crc(ais_unstuff):
        #print("AIS crc check failled")
        continue

    #Try to convert LSB->MSB
    ais_msb = message.lsb_msb(ais_unstuff) 
    nemea_text = message.to_nmea(ais_msb)
    #nemea_text = message.to_nmea(ais_unstuff)
    print("NMEA Text: {}".format(nemea_text))
    


#trial = bitstring.BitArray("0b000001000100101101010111011100001010010000000000000000000000110111001000110111100001101000011100011101110010011111101011110000110101010111010000000000001000011000011011")
#Add in checksum
#trial.append('0b1011110111000011')
#nemea_text = message.to_nmea(trial)
#print("NMEA Text Trial: {}".format(nemea_text)) 
#!AIVDM,1,1,,A,14eGL:@000o8oQ`LMjOchmG@08HK,0*40
    



