import time
import schedule
from main import run_pipeline

def job():
    print("\n==========================================")
    print("🤖 STARTING AUTOMATED MARWARI SHORT PIPELINE")
    print("==========================================")
    try:
        run_pipeline()
        print("✅ Pipeline execution finished successfully!\n")
    except Exception as e:
        print(f"❌ Error during pipeline execution: {e}\n")

# Run immediately upon launch
job()

# Schedule to repeat every 4 hours
schedule.every(4).hours.do(job)

print("⏰ Automation Scheduler actively running every 4 hours...")
print("Keep this terminal window open to maintain automation.\n")

while True:
    schedule.run_pending()
    time.sleep(60)