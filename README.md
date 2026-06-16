# pyAIS
An AIS (Automatic Identification System) receiver written entirely in Python. It can decode AIS messages from an RTL-SDR or from recorded sample files.

## Features

- Real-time AIS message decoding from an RTL-SDR.
- Support for satellite AIS (long-range) frequencies.
- Ability to process recorded sample files (e.g., `.wav`, `.raw`) for benchmarking or playback.
- Multiprocessing-based architecture for efficient decoding.

## Prerequisites

- Python 3.x
- RTL-SDR hardware (for real-time reception)
- RTL-SDR drivers installed on your system

## Usage

Run using a RTL-SDR to receive over the air signals.  
`pyais.py`

Run using a RTL-SDR to receive over the air signals. Satellite (long range AIS) frequencies.  
`pyais.py -s`

Run with a sample file instead of SDR input. (For benchmarking)  
`pyais.py -f [filename]`  

#### Possible file names (messages decoded)

* "_LA_LB_Snippet16_Proc.wav" (85)
* "helsinki-210-messages.raw" (153)



