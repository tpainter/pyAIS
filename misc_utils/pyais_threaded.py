#
# Heavily modified from pyFMradio Copyright 2014 David Swiston
# https://github.com/dswiston/pyFmRadio/blob/master/pyFmRadio.py

import threading
import Queue
import struct
import cmath
import numpy as np
from sys import stdout, stderr
from scipy import signal
from rtlsdr import RtlSdr


class FileReader(threading.Thread):
  def run(self):

    fid = open('sample','rb');
    blkSize = 1024*1000;
    data = fid.read(blkSize);
    while len(data) >= 1:
      data = ConvertData(data,len(data));
      dataQueue.put(data);
      dataQueue.join();
      data = fid.read(blkSize);
            

# Callback used by rtlsdr library, is called when data is ready
def sdrCallback(samples, rtlsdr_obj):
  # Put data on the queue
  dataQueue.put(np.array(samples,dtype=np.complex64));


class FMDemod(threading.Thread):
  def run(self):
    
    # Define the FIR filter taps used to extract the audio channels
    # (90 taps, equiripple, fc = 19KHz, +/-0.4dB ripple in pass band, -47dB stop-band)
    audioFilt = np.array([-0.00287983581133987,-0.000926407885047457,-0.000635251149646470,1.62845117817972e-05,0.00101916904478077,0.00229943112316492,0.00371371303782623,0.00506045151836540,0.00610736757778672,0.00662771338675820,0.00644014551958777,0.00544825751160880,0.00367332418708154,0.00127145849802163,-0.00147184344296973,-0.00417153634486715,-0.00639395493204246,-0.00772265459702439,-0.00783097318267360,-0.00655054644922716,-0.00392290604321896,-0.000222050906968737,0.00405977873813144,0.00826470411817517,0.0116557586699066,0.0135276814247624,0.0133274609455304,0.0107664845536791,0.00590519748125791,-0.000806134283814829,-0.00854123766576385,-0.0161694590376135,-0.0223801909792768,-0.0258466830262674,-0.0254085058655117,-0.0202474878245569,-0.0100315190547527,0.00499593742645088,0.0239963553790494,0.0455936584130458,0.0680052492125116,0.0892321839791224,0.107284945330503,0.120415688114799,0.127326567918114,0.127326567918114,0.120415688114799,0.107284945330503,0.0892321839791224,0.0680052492125116,0.0455936584130458,0.0239963553790494,0.00499593742645088,-0.0100315190547527,-0.0202474878245569,-0.0254085058655117,-0.0258466830262674,-0.0223801909792768,-0.0161694590376135,-0.00854123766576385,-0.000806134283814829,0.00590519748125791,0.0107664845536791,0.0133274609455304,0.0135276814247624,0.0116557586699066,0.00826470411817517,0.00405977873813144,-0.000222050906968737,-0.00392290604321896,-0.00655054644922716,-0.00783097318267360,-0.00772265459702439,-0.00639395493204246,-0.00417153634486715,-0.00147184344296973,0.00127145849802163,0.00367332418708154,0.00544825751160880,0.00644014551958777,0.00662771338675820,0.00610736757778672,0.00506045151836540,0.00371371303782623,0.00229943112316492,0.00101916904478077,1.62845117817972e-05,-0.000635251149646470,-0.000926407885047457,-0.00287983581133987]);
    # Define the decimation rate to convert from the sampling rate to the audio rate        
    audioDec = 6;
    
    # Create the audio filter states, initially filled w/zeros
    audioFiltStateLplusR = np.zeros((audioDec,np.size(audioFilt)/audioDec-1),dtype=np.complex64);
    audioFiltStateLminusR = np.zeros((audioDec,np.size(audioFilt)/audioDec-1),dtype=np.complex64);

    # Create the filter used to isolate the RBDS signal and decimate    
    rbdsFilt = np.array([-0.000595132554341352,-0.000742064608671778,-0.00115013457354376,-0.00164957369360677,-0.00222601333251697,-0.00285164595013564,-0.00348332573313317,-0.00406512187419635,-0.00452588003705075,-0.00478434305737503,-0.00475038089559053,-0.00433133606942404,-0.00343720332205046,-0.00198668816938035,8.54666416961390e-05,0.00282273368226101,0.00624023041591508,0.0103209856663588,0.0150128155310789,0.0202274377622374,0.0258419051023901,0.0317019442206187,0.0376284217223794,0.0434248440941824,0.0488869036949368,0.0538125666499761,0.0580126554373665,0.0613214000187263,0.0636053991924333,0.0647714233089498,0.0647714233089498,0.0636053991924333,0.0613214000187263,0.0580126554373665,0.0538125666499761,0.0488869036949368,0.0434248440941824,0.0376284217223794,0.0317019442206187,0.0258419051023901,0.0202274377622374,0.0150128155310789,0.0103209856663588,0.00624023041591508,0.00282273368226101,8.54666416961390e-05,-0.00198668816938035,-0.00343720332205046,-0.00433133606942404,-0.00475038089559053,-0.00478434305737503,-0.00452588003705075,-0.00406512187419635,-0.00348332573313317,-0.00285164595013564,-0.00222601333251697,-0.00164957369360677,-0.00115013457354376,-0.000742064608671778,-0.000595132554341352])
    # Define the decimation rate to convert from the sampling rate to the RBDS rate
    rbdsDec = 10;
    # Create the Root Raised Cosine filter used to perform the RBDS matched filtering
    rrCosFilt = np.array([-0.00281562025759368,-0.00243888516957360,-0.000999844542191435,0.00107593094803098,0.00303973034012925,0.00406700703874643,0.00357325036472412,0.00148757358716287,-0.00162769040855969,-0.00468282782128020,-0.00639101106088724,-0.00573885664637510,-0.00244729848210667,0.00275023551791118,0.00815158917037663,0.0115038199095970,0.0107291667736578,0.00477805894125585,-0.00564522027360720,-0.0177416940767021,-0.0268422464557264,-0.0272355771946698,-0.0134654388344483,0.0181901542149565,0.0684322485815653,0.134211232278632,0.208806091825802,0.282774215523415,0.345612930084173,0.387782741962203,0.402633696835896,0.387782741962203,0.345612930084173,0.282774215523415,0.208806091825802,0.134211232278632,0.0684322485815653,0.0181901542149565,-0.0134654388344483,-0.0272355771946698,-0.0268422464557264,-0.0177416940767021,-0.00564522027360720,0.00477805894125585,0.0107291667736578,0.0115038199095970,0.00815158917037663,0.00275023551791118,-0.00244729848210667,-0.00573885664637510,-0.00639101106088724,-0.00468282782128020,-0.00162769040855969,0.00148757358716287,0.00357325036472412,0.00406700703874643,0.00303973034012925,0.00107593094803098,-0.000999844542191435,-0.00243888516957360,-0.00281562025759368])
    # Create the RBDS filter states, initially filled w/zeros
    rbdsFiltState = np.zeros((rbdsDec,np.size(rbdsFilt)/rbdsDec-1),dtype=np.complex64);
    rrCosFiltState = np.zeros(np.size(rrCosFilt)-1,dtype=np.complex64);
    
    # FM carrier frequency
    pilotFreq = 19e3;
    # Define the raw sampling rate
    fs = 250e3;
    
    # Create the IIR peaking filter that isolates the carrier
    # This is important for demodulating the DSB-CS R-L signal that is used for stereo FM
    filtFreq = pilotFreq / (fs) * 2;
    bw = 5 / (fs);
    [pilotFiltB,pilotFiltA] = PeakFilterDesign(filtFreq,bw);
    pilotFiltState = np.zeros(np.size(pilotFiltB)-1,dtype=np.float32);
    
    # Create the RDS object used for RDS decoding
    rbds = Rds(fs/rbdsDec);
       
    while(1):
      
      # Get the next chunk of raw data
      data = dataQueue.get();
      dataQueue.task_done();
      
      # Perform the FM Demodulation step
      fmDemod = FmDemodulate(data);
      # Add an element to keep a proper size for the polyphase filtering
      fmDemod = np.concatenate(([0],fmDemod));
      
      # Filter and decimate the input to extract the L+R signal (20.833KHz)
      (audioDataLplusR,audioFiltStateLplusR) = PolyphaseDecimate(audioFilt,fmDemod,[],audioFiltStateLplusR,audioDec);
      audioDataLplusR = np.real(audioDataLplusR);

      # Isolate the pilot signal
      (pilot,pilotFiltState) = lfilter(pilotFiltB,pilotFiltA,fmDemod,zi=pilotFiltState);
      # Scale the pilot to full-scale since it will be used to demodulate
      pilot = pilot / np.sqrt(np.mean(pilot**2)) / np.sqrt(2);
      # Convert the pilot to a complex representation, then double the frequency
      # This signal is used demodulate the L-R DSB-SC signal 
      stereoCarrier = hilbert(pilot)**2;
      # Mix, filter, and decimate the input to extract the L-R signal (20.833KHz)
      (audioDataLminusR,audioFiltStateLminusR) = PolyphaseDecimate(audioFilt,fmDemod,stereoCarrier,audioFiltStateLminusR,audioDec);
      audioDataLminusR = np.real(audioDataLminusR);
      
      # Perform the RBDS decoding
      # First, extract the RBDS carrier, used to mix the RBDS signal to baseband (or near baseband)
      rbdsCarrier = hilbert(pilot)**(3.0);
      # Mix to baseband, filter and decimate to a lower sampling rate
      (rbdsSignal,rbdsFiltState) = PolyphaseDecimate(rbdsFilt,fmDemod,rbdsCarrier,rbdsFiltState,rbdsDec);
      # Perform matched filtering operation using root raised cosine filter
      (rbdsSignal,rrCosFiltState) = lfilter(rrCosFilt,1,rbdsSignal,zi=rrCosFiltState);
      # Input the data into the RBDS decoder and perform the decoding
      rbds.NewData(rbdsSignal);
      rbds.ProcessBlocks();
      
      stderr.write("\x1b[2J\x1b[H");
      stdout.write("Call Sign:    " + rbds.callSign + '\n');
      stdout.write("Station Type: " + rbds.ptyString + '\n');
      stdout.write("Radio Text:   " + rbds.radioText + '\n');
      
      # Scale and DC filter the audio before playing it
      (audioDataLplusR, audioDataLminusR) = ProcessAudio(audioDataLplusR,audioDataLminusR);

      # Apply the de-emphasis filter
      audioFs = fs/audioDec;
      audioDataLplusR = DeEmphasisFilter(audioDataLplusR,audioFs);
      audioDataLminusR = DeEmphasisFilter(audioDataLminusR,audioFs);

      # Using the two audio signals (L+R) and (R-L), create the stereo stereo channels
      audioDataL = audioDataLplusR + audioDataLminusR;
      audioDataR = audioDataLplusR - audioDataLminusR;

      # Multiplex the stereo channels, the ao library assumes this behavior
      # Also convert the data to 16bit signed as the audio stream assumes this format
      audioData = np.empty(len(audioDataL)*2, dtype=np.int16);
      audioData[::2] = audioDataL.astype(np.int16);
      audioData[1::2] = audioDataR.astype(np.int16);

      # If mono is desired, uncomment this line
      #audioData = audioDataLplusR.astype(np.int16);

      # Put the audio onto the queue and wait for it to be received
      audioQueue.put(audioData);
      audioQueue.join();


class AudioPlay(threading.Thread):
  def run(self):

    # Grab initial data off of the queue
    audioData = audioQueue.get();
    audioQueue.task_done();
    
    # Create the audio device
    audioObject = pyaudio.PyAudio();
    # Create stream object associated with the audio device
    # If mono is desired, change the number of channels to '1' here
    pcmStream = audioObject.open(format=pyaudio.paInt16,channels=2,rate=41666,output=True,frames_per_buffer=np.size(audioData)*2)
    
    while(1):
      # Play the audio - the Python wrapper assumes a string of bytes. . . 
      # It doesn't have to be this way but that is pyaudio's assumption
      pcmStream.write(str(bytearray(audioData)));
      # Grab new data off of the queue
      audioData = audioQueue.get();
      audioQueue.task_done();


def ProcessAudio(audio1,audio2):
    
  # Remove the DC component of the audio
  audio1 = audio1 - np.mean(audio1);
  audio2 = audio2 - np.mean(audio2);
  # Scale the audio
  audio1 = audio1 / np.max([np.abs(audio1),np.abs(audio2)]);
  audio2 = audio2 / np.max([np.abs(audio1),np.abs(audio2)]);
  # Convert to a 16bit signed representation
  audio1 = audio1 * 32768 / 2;
  audio2 = audio2 * 32768 / 2;
  
  return(audio1,audio2);
    
    
def ConvertData(tmp,blkSize):
  # Unpack the bytes of the string in data into unsigned characters
  readFormat = str(blkSize) + 'B'
  tmp = struct.unpack(readFormat,tmp);
  # Convert to a numpy array of floats
  tmp = np.asarray(tmp,dtype=np.float32);
  # Subtract 127 from the data (to convert to signed)
  tmp = tmp - 127;
  data = np.zeros(len(tmp)/2, dtype=np.complex64);
  data.real = tmp[::2];
  data.imag = tmp[1::2];
  return data
    
    
def FmDemodulate(data):
  # Calculate the complex vector between two adjacent data points
  tmp = data[1::1] * np.conjugate(data[0:-1:1]);
  # Record the angle of the complex difference vectors
  return np.angle(tmp);
    

def PolyphaseDecimate(filt,inputData,mixValues,filtState,decRate):
    
  # Decompose the input and the filter
  polyFilt = np.reshape(filt,[decRate, -1],order='F');
  polyFilt = np.flipud(polyFilt);
  polyInput = np.reshape(inputData,[decRate,-1],order='F');
  # Pre-allocate the array
  tmp = np.zeros(shape=(decRate,len(inputData)/decRate), dtype=np.complex64);

  # Perform the mixing (only if necessary)
  if len(mixValues) > 0:
    polyMix = np.reshape(mixValues,[decRate,-1],order='F');
    polyInput = polyInput * polyMix;
  
  # Perform the filtering - there are two ways out of the function
  if np.size(filtState) == 0:
    # A filter state was not passed in, ignore tracking states
    for ndx in range(decRate):
      tmp[ndx,:] = lfilter(polyFilt[ndx,:],1,polyInput[ndx,:]);
    return np.sum(tmp,axis=0);
  else:
    # A filter state was passed in. Supply it to the filter routine and pass back the updated state
    for ndx in range(decRate):
      (tmp[ndx,:],filtState[ndx,:]) = lfilter(polyFilt[ndx,:],1,polyInput[ndx,:],zi=filtState[ndx,:]);
    return (np.sum(tmp,axis=0),filtState);
        
        
def DeEmphasisFilter(audio,fs):
 
  # Calculate the # of samples to hit the -3dB point
  d = fs * 75e-6;
  # Calculate the decay between each sample
  x = np.exp(-1/d);
  # Use this information to create the filter coefficients
  b = [1-x];
  a = [1,-x];
  
  # Perform the filtering and return the result
  return lfilter(b,a,audio);


def PeakFilterDesign(freq,bw):
  # Design a 2nd order IIR peaking filter
  
  # Normalize to pi
  bw = bw*np.pi;
  freq = freq*np.pi;
  
  Gb   = 0.707945784384;
  beta = (Gb/np.sqrt(1-Gb**2))*np.tan(bw/2);
  gain = 1/(1+beta);
  
  num  = (1-gain)*np.array([1,0,-1]);
  den  = np.array([1, -2*gain*np.cos(freq), (2*gain-1)]);
  
  return (num,den);


fmDemod = FMDemod();
fileRead = FileReader();
audioPlay = AudioPlay();

dataQueue = Queue.Queue([1]);
audioQueue = Queue.Queue([1]);

sdr = RtlSdr();

# configure device
sdr.sample_rate = 250e3;  # Hz
numSampsRead = 1024*600;
freq = raw_input('Choose a station frequency: ');

try:
  freq = float(freq);
  sdr.center_freq = freq;
  sdr.gain = 'auto';
  #fileRead.start();
  fmDemod.start();
  audioPlay.start();
  sdr.read_samples_async(sdrCallback, numSampsRead);    
    
except ValueError:
  print("Invalid number");
    