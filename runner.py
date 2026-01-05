import time
import subprocess
import random
import sys
from datetime import datetime

def main():
    print("Starting runner for script.py...")
    try:
        while True:
            start_time = datetime.now()
            print(f"\n[{start_time.strftime('%Y-%m-%d %H:%M:%S')}] Starting execution loop...")
            
            # Execute the script
            process = subprocess.run([sys.executable, "script.py", "--once"])
            
            if process.returncode != 0:
                print(f"Warning: script.py exited with return code {process.returncode}")
            
            # Calculate random sleep time between 15 and 20 minutes
            wait_minutes = random.uniform(25, 40)
            wait_seconds = wait_minutes * 60
            
            next_run = time.time() + wait_seconds
            next_run_dt = datetime.fromtimestamp(next_run)
            
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Execution finished. Waiting {wait_minutes:.1f} minutes.")
            print(f"Next run scheduled for: {next_run_dt.strftime('%H:%M:%S')}")
            
            # Wait loop to allow nice KeyboardInterrupt
            while time.time() < next_run:
                time.sleep(1)

    except KeyboardInterrupt:
        print("\nRunner stopped by user.")
    except Exception as e:
        print(f"\nCritical error in runner: {e}")

if __name__ == "__main__":
    main()
