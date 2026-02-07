import sqlite3

conn = sqlite3.connect('talentai.db')
cursor = conn.cursor()

# Get all jobs without job_id
cursor.execute("SELECT id, title FROM job_descriptions WHERE job_id IS NULL")
jobs = cursor.fetchall()

print(f"Found {len(jobs)} jobs without job_id")

# Generate job_id for each job
for job_id, title in jobs:
    # Generate job_id as JOB-{id:03d}
    new_job_id = f"JOB-{job_id:03d}"
    cursor.execute("UPDATE job_descriptions SET job_id = ? WHERE id = ?", (new_job_id, job_id))
    print(f"Updated job {job_id} ({title}) with job_id: {new_job_id}")

conn.commit()

# Verify
cursor.execute("SELECT id, title, job_id FROM job_descriptions")
jobs = cursor.fetchall()
print("\nAll jobs:")
for job_id, title, custom_job_id in jobs:
    print(f"  {job_id}: {title} - Job ID: {custom_job_id}")

conn.close()
