from app.database import SessionLocal
from app.models import Client

db = SessionLocal()

clients = [
    Client(name='TechCorp Solutions', industry='Technology', contact_person='John Anderson', contact_email='john@techcorp.com', contact_phone='+1-555-100-2000', total_positions=25, positions_filled=18, positions_open=7, avg_time_to_hire=28.5, retention_rate=92.0, acceptance_rate=85.0, is_active=True),
    Client(name='Global Finance Inc', industry='Finance', contact_person='Sarah Mitchell', contact_email='sarah@globalfinance.com', contact_phone='+1-555-200-3000', total_positions=15, positions_filled=12, positions_open=3, avg_time_to_hire=22.0, retention_rate=88.0, acceptance_rate=90.0, is_active=True),
    Client(name='HealthTech Innovations', industry='Healthcare', contact_person='Dr. Emily Chen', contact_email='emily@healthtech.com', contact_phone='+1-555-300-4000', total_positions=20, positions_filled=8, positions_open=12, avg_time_to_hire=35.0, retention_rate=78.0, acceptance_rate=72.0, is_active=True),
    Client(name='RetailMax Group', industry='Retail', contact_person='Michael Brown', contact_email='michael@retailmax.com', contact_phone='+1-555-400-5000', total_positions=30, positions_filled=22, positions_open=8, avg_time_to_hire=25.0, retention_rate=85.0, acceptance_rate=80.0, is_active=True),
    Client(name='EduLearn Platform', industry='Education', contact_person='Lisa Johnson', contact_email='lisa@edulearn.com', contact_phone='+1-555-500-6000', total_positions=12, positions_filled=10, positions_open=2, avg_time_to_hire=20.0, retention_rate=95.0, acceptance_rate=88.0, is_active=True),
    Client(name='AutoDrive Systems', industry='Automotive', contact_person='Robert Taylor', contact_email='robert@autodrive.com', contact_phone='+1-555-600-7000', total_positions=18, positions_filled=6, positions_open=12, avg_time_to_hire=40.0, retention_rate=70.0, acceptance_rate=65.0, is_active=True),
    Client(name='CloudNet Services', industry='Cloud Computing', contact_person='Amanda White', contact_email='amanda@cloudnet.com', contact_phone='+1-555-700-8000', total_positions=22, positions_filled=16, positions_open=6, avg_time_to_hire=26.0, retention_rate=90.0, acceptance_rate=82.0, is_active=True),
    Client(name='MediaStream Co', industry='Media & Entertainment', contact_person='David Martinez', contact_email='david@mediastream.com', contact_phone='+1-555-800-9000', total_positions=10, positions_filled=9, positions_open=1, avg_time_to_hire=18.0, retention_rate=94.0, acceptance_rate=92.0, is_active=True)
]

# Clear existing
db.query(Client).delete()
db.commit()

# Add new
for client in clients:
    db.add(client)
db.commit()

print(f'Added {len(clients)} clients successfully!')
db.close()
