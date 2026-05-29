import sys
sys.path.append(r'd:\VWings24x7-App-Backend')
import os
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import the Course model (assuming it's in models/courses/course_models.py)
from models.courses.course_models import Course

# Connect to the local PostgreSQL database
engine = create_engine('postgresql://postgres:password@localhost/vwings24x7_db')
Session = sessionmaker(bind=engine)
session = Session()

base_url = 'https://appbackend.vwings247.me/'
live_courses = requests.get('https://appbackend.vwings247.me/api/courses/get-all').json()

count = 0
for live_c in live_courses:
    if live_c.get('course_photo'):
        # Find the matching course in local DB by course_code
        local_c = session.query(Course).filter_by(course_code=live_c['course_code']).first()
        if local_c:
            # Download the image
            rel_path = live_c['course_photo'].replace('/', os.sep)
            abs_path = os.path.join(r'd:\VWings24x7-App-Backend', rel_path)
            
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            img_url = base_url + live_c['course_photo']
            
            print(f"Downloading {img_url} for {local_c.course_code}")
            img_res = requests.get(img_url)
            if img_res.status_code == 200:
                with open(abs_path, 'wb') as f:
                    f.write(img_res.content)
                
                # Update the database
                local_c.course_photo = live_c['course_photo']
                count += 1
            else:
                print(f"Failed to download image for {local_c.course_code}")

session.commit()
session.close()
print(f"Fixed {count} images.")
