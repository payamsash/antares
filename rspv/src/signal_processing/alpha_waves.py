# src/signal_processing/alpha_waves.py
# pylint: disable=no-member

import random
import time
from pathlib import Path
import numpy as np
from pythonosc import udp_client, dispatcher, osc_server


def receive_data_from_LSL(sample_rate=0.01):
    """
    Receives real-time data from an LSL stream and calculates alpha power differences 
    between two EEG channels ('C3' and 'C4') in the alpha frequency band (8-13 Hz).

    This function records data, performs FFT to compute power spectral density,
    and yields the alpha power difference over time.

    Yields:
        float: The alpha power difference between channels 'C3' and 'C4'.

    Raises:
        FileNotFoundError: If the specified recording directory is invalid or inaccessible.
        KeyError: If the specified stream name does not exist in the LSL stream receiver.
    """
    # Define the LSL stream name and recording directory
    stream_name = 'BrainVision RDA'  # LSL stream name (e.g., 'RDA 127.0.0.1:51244')
    record_dir = Path('D:\\Data\\ASMR\\raws').expanduser()  # Path to save the recorded data

    # Initialize the recorder to save raw data locally
    recorder = bsl.StreamRecorder(
        record_dir=record_dir,
        fname=None,
        stream_name=stream_name,
        fif_subdir=False,
        verbose=False
    )
    recorder.start()

    # Initialize the receiver for streaming data
    receiver = bsl.StreamReceiver(bufsize=4, winsize=2, stream_name=stream_name)
    
    # Calculate the FFT window size and sample spacing
    winsize_in_samples = receiver.streams['BrainVision RDA'].sample_rate * receiver.winsize
    sample_spacing = 1. / receiver.streams['BrainVision RDA'].sample_rate
    
    # Define the frequency range for alpha waves (8-13 Hz)
    frequencies = np.fft.rfftfreq(n=int(winsize_in_samples), d=sample_spacing)
    smr_band = np.where(np.logical_and(8 <= frequencies, frequencies <= 13))[0]
    
    # Define a Hanning window for FFT to reduce spectral leakage
    fft_window = np.hanning(winsize_in_samples)
    
    # Timer to track the resting state phase (10 seconds)
    phase_timer = bsl.utils.Timer()
    
    while phase_timer.sec() <= 10:  # Process data for the first 10 seconds
        # Acquire a new data window
        receiver.acquire()
        raw, samples = receiver.get_window(return_raw=True)

        # Skip processing if the sample count doesn't match the expected window size
        if samples.shape[0] != winsize_in_samples:
            continue

        # Extract data for EEG channels 'C3' and 'C4'
        data = raw.pick(picks=['C3', 'C4']).get_data()
        
        # Apply the FFT window to the data
        data = np.multiply(data, fft_window)

        # Perform FFT and calculate power spectral density
        fftval = np.abs(np.fft.rfft(data, axis=1) / data.shape[-1])
        
        # Calculate the alpha power difference between 'C3' and 'C4'
        alpha_power = abs(
            np.average(np.square(fftval[:, smr_band]), axis=1)[1] -
            np.average(np.square(fftval[:, smr_band]), axis=1)[0]
        )

        # Yield the calculated alpha power difference
        yield alpha_power
        
        # Pause briefly before processing the next window
        time.sleep(sample_rate)

def generate_live_alpha_signal(
    duration, ip="127.0.0.1", port=5005, address="/alpha", power_range=(1, 50), step=1.0, sample_rate=0.1
):
    """
    Generate a live alpha brain wave signal with gradual transitions and send it via OSC.
    
    Args:
        duration (float): Total duration (in seconds) for generating the signal.
        ip (str): IP address of the OSC server.
        port (int): Port number for the OSC server.
        address (str): OSC address for sending the signal.
        power_range (tuple): Range of alpha wave power (min, max).
        step (float): Step size for adjusting the frequency towards the target.
    
    Yields:
        float: The current alpha wave power being sent.
    """
    try:
        # Set up OSC client
        osc_client = udp_client.SimpleUDPClient(ip, port)
        
        start_time = time.time()
        elapsed_time = 0
        current_freq = random.uniform(*power_range)  # Start with a random frequency within the range
        target_freq = random.uniform(*power_range)  # Set an initial target frequency

        while elapsed_time < duration:
            # Gradually adjust the current frequency towards the target frequency
            if abs(current_freq - target_freq) < step:
                # If the current frequency is close to the target, pick a new target frequency
                target_freq = random.uniform(*power_range)
            else:
                # Smoothly move the current frequency towards the target
                current_freq += step if target_freq > current_freq else -step

            # Debug: Uncomment this line to see the current state
            #print(f"Time: {elapsed_time:.1f}s, Alpha Wave Power: {current_freq:.2f} uV^2, Address: {address}")
            osc_client.send_message(address, (None, None, current_freq))

            # Wait for 1 second before generating the next value
            time.sleep(sample_rate)
            
            # Update elapsed time
            elapsed_time = time.time() - start_time

    except Exception as e:
        print(f"Error in generate_live_alpha_signal: {e}")

def read_signal_from_file(file_path, duration, sample_rate=0.1, map_func=lambda x: x):
    """
    Reads alpha brainwave signals from a file and yields the processed values.

    This function streams data from a file, mimicking real-time signal processing. 
    It reads the file line by line, applies a mapping function to each value, 
    and yields the resulting signal values at the specified sample rate.

    Args:
        file_path (str): Path to the file containing alpha wave signal values.
        duration (float): Total duration (in seconds) for reading the file.
        sample_rate (float, optional): Interval (in seconds) between successive signal readings. Default is 0.1 seconds.
        map_func (callable, optional): A function to transform the raw signal value. Default is identity (returns the input value unchanged).

    Yields:
        float: The processed alpha power value.
    
    Raises:
        ValueError: If the file contains non-numeric values that cannot be converted to float.
        FileNotFoundError: If the specified file does not exist.
    """
    start_time = time.time()  # Record the start time for tracking elapsed time
    elapsed_time = 0  # Initialize the elapsed time counter

    try:
        with open(file_path, "r") as file:  # Open the file for reading
            while True:
                for line in file:
                    # Strip leading/trailing whitespace and convert to float
                    try:
                        line = line.strip()
                        alpha_power = float(line)
                    except ValueError:
                        raise ValueError(f"Invalid value in file: {line} is not a valid number.")

                    # Apply the mapping function to the signal value
                    alpha_power = map_func(alpha_power)

                    # Yield the processed signal value
                    yield alpha_power

                     # Wait for the next sample interval
                    time.sleep(sample_rate)

                # If we finished the file but still within duration → restart from top
                file.seek(0)

    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")


# Example usage
if __name__ == "__main__":
    # Generate and send live alpha waves for 10 seconds
    # for freq in receive_data_from_LSL():
        
    #     pass
    for freq in generate_live_alpha_signal(10):
        pass

