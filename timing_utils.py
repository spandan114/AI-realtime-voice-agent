# timing_utils.py
import time
from functools import wraps
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
import json
from colorama import Fore
from tabulate import tabulate

@dataclass
class TimingMetric:
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    
class ProcessTimer:
    def __init__(self):
        self.metrics: Dict[str, List[TimingMetric]] = {}
        self.process_order = [
            "transcription_generation",
            "response_generation",
            "text_splitting",
            "audio_generation",
            "audio_playback"
        ]
        self.process_names = {
            "transcription_generation": "Speech to Text",
            "response_generation": "LLM Processing",
            "text_splitting": "Text Splitting",
            "audio_generation": "Audio Generation",
            "audio_playback": "Audio Playback"
        }
        
    def start(self, process_name: str) -> None:
        if process_name not in self.metrics:
            self.metrics[process_name] = []
        self.metrics[process_name].append(TimingMetric(start_time=time.time()))
        
    def stop(self, process_name: str) -> None:
        if process_name in self.metrics and self.metrics[process_name]:
            metric = self.metrics[process_name][-1]
            metric.end_time = time.time()
            metric.duration = metric.end_time - metric.start_time
            
    def get_latest_duration(self, process_name: str) -> Optional[float]:
        if process_name in self.metrics and self.metrics[process_name]:
            return self.metrics[process_name][-1].duration
        return None
        
    def get_average_duration(self, process_name: str) -> Optional[float]:
        if process_name in self.metrics:
            durations = [m.duration for m in self.metrics[process_name] if m.duration is not None]
            if durations:
                return sum(durations) / len(durations)
        return None

    def calculate_total_time(self) -> dict:
        """Calculate total time for latest interaction and average"""
        latest_total = 0
        average_total = 0
        
        for process_name in self.process_order:
            if process_name in self.metrics:
                latest = self.get_latest_duration(process_name)
                average = self.get_average_duration(process_name)
                if latest:
                    latest_total += latest
                if average:
                    average_total += average
                    
        return {
            "latest": latest_total,
            "average": average_total
        }
    
    def print_metrics(self) -> None:
        headers = ["Process", "Latest (s)", "Average (s)", "Total Runs"]
        rows = []
        
        # Add process rows in specified order
        for process_name in self.process_order:
            if process_name in self.metrics:
                durations = [m.duration for m in self.metrics[process_name] if m.duration is not None]
                if durations:
                    display_name = self.process_names.get(process_name, process_name)
                    rows.append([
                        display_name,
                        f"{durations[-1]:.3f}",
                        f"{sum(durations) / len(durations):.3f}",
                        len(durations)
                    ])
        
        # Calculate and add total time
        totals = self.calculate_total_time()
        rows.append([
            f"{Fore.YELLOW}Total Time{Fore.RESET}",
            f"{Fore.YELLOW}{totals['latest']:.3f}{Fore.RESET}",
            f"{Fore.YELLOW}{totals['average']:.3f}{Fore.RESET}",
            ""
        ])
        
        # Print the table
        print(f"\n{Fore.CYAN}=== Process Timing Metrics ==={Fore.RESET}")
        print(tabulate(rows, headers=headers, tablefmt="grid", floatfmt=".3f"))
    
    def save_metrics(self, filename: str) -> None:
        metrics_data = {
            'timestamp': datetime.now().isoformat(),
            'processes': {}
        }
        
        for process_name in self.process_order:
            if process_name in self.metrics:
                durations = [m.duration for m in self.metrics[process_name] if m.duration is not None]
                if durations:
                    metrics_data['processes'][process_name] = {
                        'average_duration': sum(durations) / len(durations),
                        'latest_duration': durations[-1],
                        'total_runs': len(durations),
                        'all_durations': durations
                    }
        
        # Add total times
        totals = self.calculate_total_time()
        metrics_data['totals'] = totals
                
        with open(filename, 'w') as f:
            json.dump(metrics_data, f, indent=2)

# Timer decorator for easy timing of functions
"""
How it works step by step:

1. When you decorate a method with @time_process("some_name"):
   - The decorator is initialized with the process_name
   - The method is wrapped with the timing functionality

2. When the decorated method is called:
   - wrapper() function executes first
   - It checks if the class instance (self) has a timer
   - If timer exists:
     a. Records start time via timer.start()
     b. Executes the original method
     c. Records end time via timer.stop()
     d. Returns the method's result
   - If no timer:
     - Just runs the original method without timing

3. The timing data is stored in ProcessTimer's metrics dictionary:
   self.metrics = {
       "process_name": [
           TimingMetric(
               start_time=1234.5,    # When process started
               end_time=1236.7,      # When process ended
               duration=2.2          # Total time taken
           ),
           # One TimingMetric for each time the method is called
       ]
   }

4. You can view the timing results using:
   instance.timer.print_metrics()
"""
def time_process(process_name: str):
    """
    A decorator that measures the execution time of class methods.
    
    This decorator works with classes that have a 'timer' attribute (instance of ProcessTimer).
    It automatically tracks the start and end times of the decorated method and stores the timing metrics.
    
    Args:
        process_name (str): Name identifier for the process being timed (e.g., "audio_generation")
        
    Example usage:
        class MyClass:
            def __init__(self):
                self.timer = ProcessTimer()
                
            @time_process("my_process")
            def my_method(self):
                # Method code here
                pass
    """
    # Level 1: Outer function that takes the process name as parameter
    def decorator(func):
        # Level 2: Takes the function to be decorated
        # @wraps preserves the original function's metadata (name, docstring, etc.)
        @wraps(func)
        # Level 3: Wrapper that handles the actual function call
        # args[0] is 'self' in class methods
        # Check if the class instance has a timer attribute
        def wrapper(*args, **kwargs):
            if hasattr(args[0], 'timer'):
                # Get the ProcessTimer instance from the class
                timer = args[0].timer
                # Start timing this process
                # This adds a new TimingMetric to ProcessTimer.metrics[process_name]
                timer.start(process_name)
                # Execute the actual function with its arguments
                # If method is my_method(self, x, y), then:
                # args[0] is self
                # args[1:] would be x, y
                # kwargs would be any named parameters
                result = func(*args, **kwargs)
                timer.stop(process_name)
                return result
            return func(*args, **kwargs)
        return wrapper
    return decorator


