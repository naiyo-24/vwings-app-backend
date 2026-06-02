import time

import random

def generate_student_id(created_at=None):
	"""
	Generate a student ID in the pattern: STUDENT + timestamp + random digits
	"""
	if created_at is None:
		ts = int(time.time())
	else:
		ts = int(created_at.timestamp())
	rand_str = str(random.randint(100, 999))
	return f"STU{str(ts)[-5:]}{rand_str}"
