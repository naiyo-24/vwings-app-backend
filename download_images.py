import requests, json, os

try:
    courses = requests.get('http://localhost:8000/api/courses/get-all').json()
    base_url = 'https://appbackend.vwings247.me/'
    count = 0
    
    for c in courses:
        if c.get('course_photo'):
            # The path from DB looks like "uploads/courses/COURSEID/photo.ext" or similar
            # Ensure it's correctly joined
            rel_path = c['course_photo'].replace('/', os.sep)
            abs_path = os.path.join(r'd:\VWings24x7-App-Backend', rel_path)
            
            # Create directories
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            
            # Download image
            img_url = base_url + c['course_photo']
            print(f"Downloading {img_url} -> {abs_path}")
            
            img_res = requests.get(img_url)
            if img_res.status_code == 200:
                with open(abs_path, 'wb') as f:
                    f.write(img_res.content)
                count += 1
            else:
                print(f"Failed to download {img_url}: {img_res.status_code}")
                
    print(f"Successfully downloaded {count} images.")
except Exception as e:
    print(f"Error: {e}")
