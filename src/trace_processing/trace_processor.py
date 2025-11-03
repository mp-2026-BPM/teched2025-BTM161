import os
import glob
from typing import List
from .log_generator import LogGenerator
import pandas as pd
from datetime import datetime

class TraceProcessor:    
    def __init__(self, base_path: str = "./mlruns"):
        self.base_path = base_path
        
    def find_trace_files(self) -> List[str]:
        """
        Find all traces.json files in the MLflow directory structure.
        
        Returns:
            List of file paths to trace JSON files
        """
        pattern = os.path.join(self.base_path, "**/traces/**/artifacts/traces.json")
        trace_files = glob.glob(pattern, recursive=True)
        
        # Sort files by modification time (newest first) for better processing order
        trace_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        return trace_files
    
    def process_all_traces(self, export_as_json: bool = False):
        """
        Process all trace files found in the MLflow directory.
        """

        print("🔍 Searching for trace files...")
        trace_files = self.find_trace_files()
        
        if not trace_files:
            print("❌ No trace files found in ./mlruns directory")
            return {"total": 0, "successful": 0, "failed": 0}
        
        print(f"📁 Found {len(trace_files)} trace files")
        
        
        successful_ingestions = 0
        failed_ingestions = 0

        combined_logs = pd.DataFrame()
        
        for i, file_path in enumerate(trace_files, 1):
            print(f"\t📂 Processing trace {i}/{len(trace_files)}: {file_path}")
            
            log_generator = LogGenerator()
            try:
                trace_event_log = log_generator.generate_event_log_df(file_path)
                combined_logs = pd.concat([combined_logs, trace_event_log], ignore_index=True)
                successful_ingestions += 1
            except Exception as e:
                print(f"   ❌ Failed to generate event log for {file_path}: {e}")
                failed_ingestions += 1
                continue
        
        # Sort combined logs by timestamp
        combined_logs.sort_values(by="time:timestamp", inplace=True)
        

        self._generate_log_file(combined_logs, "./generated_event_log", json_format=export_as_json)

        print(f"\n📈 Processing Summary:")
        print(f"   📊 Total trace files processed: {len(trace_files)}")
        print(f"   ✅ Successful: {successful_ingestions}")
        print(f"   ❌ Failed: {failed_ingestions}")
        
        if successful_ingestions > 0:
            print(f"\nLog generation process completed successfully!")
        if len(trace_files) == 0:
            print("\nNo trace files found. Make sure you have completed some coffee shop interactions first.")
            print("💡 Go back to step 4 and create some orders to generate trace data.")
        
        return

    def _generate_log_file(self, dataframe: pd.DataFrame, output_path: str, json_format: bool = False):
        """
        Generate a log file from the given DataFrame.
        
        Args:
            dataframe: The DataFrame containing event log data
            output_path: The path to save the generated log file
        """
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")[:-3]  # UTC timestamp with ms
        filename = f"{timestamp}.eventlog"
        if json_format:
            filename += ".json"
        else:
            filename += ".csv"

        file_path = os.path.join(output_path, filename)
        
        try:
            if json_format:
                dataframe.to_json(file_path, orient="index")
            else:
                dataframe.to_csv(file_path, index=False)
            print(f"\n✅ Log file generated at {file_path}")
        except Exception as e:
            print(f"\n″❌ Failed to generate log file at {file_path}: {e}")
