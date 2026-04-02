import os
import json

# Bug 1: hardcoded password (security issue)
PASSWORD = "admin123"
DB_HOST = "localhost"

def calculate_average(numbers):
    # Bug 2: no check for empty list (division by zero)
    total = 0
    for n in numbers:
        total = total + n
    return total / len(numbers)

def read_user_data(user_id):
    # Bug 3: SQL injection vulnerability
    query = "SELECT * FROM users WHERE id = " + user_id
    return query

def save_to_file(filename, data):
    # Bug 4: file never closed (resource leak)
    f = open(filename, "w")
    f.write(data)

def parse_config(config_string):
    # Bug 5: no error handling for invalid JSON
    config = json.loads(config_string)
    return config

def get_user_age(user):
    # Bug 6: KeyError if 'age' key doesn't exist
    return user["age"]

scores = [85, 90, 78, 92, 88]
print("Average score:", calculate_average(scores))

empty = []
print("Average of empty:", calculate_average(empty))
