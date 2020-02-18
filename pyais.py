import argparse
from multiprocessing import Pipe

from ais import complex_demod as simple_demod
from ais import message


if __name__ == "__main__":
    #Setup commandline parsing
    parser = argparse.ArgumentParser(description='Decode AIS messages from an SDR.')
    parser.add_argument('-f', '--file', default=False, action='store_true', dest='from_file', help='Process samples from a file instead of a radio. Default false')
    parser.add_argument('-s', '--sat', default=False, action='store_true', dest='satellite', help='Tune SDR to satellite AIS frequencies. Default false')
    
    args = parser.parse_args()
    
    #Setup pipes for multiprocessing
    channel_A_samples_out, channel_A_samples_in = Pipe(False)    
    channel_B_samples_out, channel_B_samples_in = Pipe(False) 
    channel_A_bits_out, channel_A_bits_in = Pipe(False)    
    channel_B_bits_out, channel_B_bits_in = Pipe(False) 
    
    if args.from_file:
        from ais import fileread
        
        sample_rate = 48000
        center_freq = 161.975 * 1e6 #161.975Mhz
        decimate = 1
        stats_rate = 30
        f = []
        #f.append(["recordings\\2018-07-15-test-161975000-p51-g30-s48k.raw", "8s"]) # 3
        
        #f.append(["recordings\_LA_LB_Snippet16_Proc.wav"]) #kaiser=98
        #f.append(["recordings\long-beach-160-messages.wav"]) #same as above, only 8bit
        #f.append(["recordings\helsinki-210-messages.raw", "16s"]) #46
        f.append(["recordings\gnuais-stereo-2rx.raw", "16d"]) #Same file as above : 61 total
        
        #f.append(["recordings\\2015-04-19-test-161975000-p45-s48k.raw", "8s"]) #13
        #f.append(["recordings\\2015-04-19-test-162025000-p45-s48k.raw", "8u"]) #16
        #f.append(["recordings\\2015-04-19-test-161975000-p50-s48k.raw", "8u"]) #19
        #f.append(["recordings\\2015-04-19-test-162025000-p50-s48k.raw", "8u"]) #43
        
        #SDR = radio.RtlReceiver(sample_rate, center_freq, gain, ppm, channel_A_samples_in, channel_B_samples_in, f, satellite = False)
        SDR = fileread.FromFile(sample_rate, center_freq, channel_A_samples_in, channel_B_samples_in, f, satellite = False)
    else: 
        from ais import radio
        
        sample_rate = 1.2288 * 1e6 
        if args.satellite:
            center_freq = 156.8 * 1e6
        else:
            center_freq = 162.0 * 1e6
        gain = 33 #20 #33.8 #12.5 #14.4 #15.7 #18
        ppm = 51 #65 #66
        decimate = 8 #32   
        stats_rate = 2*60     
        SDR = radio.RtlReceiver(sample_rate, center_freq, gain, ppm, channel_A_samples_in, channel_B_samples_in, local_file = None, satellite = args.satellite)
        
    Demod_A = simple_demod.ProcessSamples(sample_rate, 'A', decimate, channel_A_samples_out, channel_A_bits_in)
    Demod_B = simple_demod.ProcessSamples(sample_rate, 'B', decimate, channel_B_samples_out, channel_B_bits_in)
    AIS_a = message.ProcessAISBits("A", channel_A_bits_out, stats_rate)
    AIS_b = message.ProcessAISBits("B", channel_B_bits_out, stats_rate)
    
    SDR.daemon = True
    Demod_A.daemon = True
    Demod_B.daemon = True
    AIS_a.daemon = True
    AIS_b.daemon = True
    
    
    Demod_A.start()
    Demod_B.start()
    AIS_a.start()
    AIS_b.start()
    SDR.start()

    Demod_A.join()
    Demod_B.join()    
    AIS_a.join()
    AIS_b.join()
    SDR.join()

