# pyAIS
 AIS receiver written entirely in Python

# Usage:
Run using a RTL-SDR to receive over the air signals.  
`pyais.py`

Run using a RTL-SDR to receive over the air signals. Satellite (long range AIS) frequencies.  
`pyais.py -s`

Run with a sample file instead of SDR input. (For benchmarking)  
`pyais.py -f [filename]`  

#### Possible file names (messages decoded):
* "_LA_LB_Snippet16_Proc.wav" (85)
* "helsinki-210-messages.raw" (153)
