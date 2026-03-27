"""Integration test — requires live UC API credentials."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unicommerce.client import UnicommerceClient
from datetime import datetime, timedelta

def test_export_job_lifecycle():
    """Create export job, poll, download CSV."""
    client = UnicommerceClient()
    client.authenticate()
    client.discover_facilities()
    facility = client.facilities[0]

    # 2-day window ending yesterday
    end = datetime.now().replace(hour=23, minute=59, second=59)
    start = end - timedelta(days=2)
    start = start.replace(hour=0, minute=0, second=0)

    job_code = client.create_export_job(
        facility=facility,
        start_date=start,
        end_date=end,
    )
    assert job_code, "Job code should be returned"

    status, file_path = client.poll_export_job(job_code, facility=facility, timeout=120)
    assert status == "COMPLETE", f"Expected COMPLETE, got {status}"
    assert file_path, "File path should be returned"

    csv_text = client.download_export_csv(file_path)
    assert csv_text, "CSV should not be empty"
    lines = csv_text.strip().split('\n')
    assert 'SKU Code' in lines[0], f"Header should contain SKU Code: {lines[0]}"
    print(f"Downloaded {len(lines)-1} rows from {facility}")

if __name__ == "__main__":
    test_export_job_lifecycle()
    print("PASS")
