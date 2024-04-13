# 🚨 Don't change the code below 👇
student_heights = input("Input a list of student heights ").split()
for n in range(0, len(student_heights)):
  student_heights[n] = int(student_heights[n])
# 🚨 Don't change the code above 👆


#Write your code below this row 👇
# total_height = sum(student_heights)
# number_student = len(student_heights)
# print(total_height, "\n", number_student)
# average_height = total_height / number_student
# print (average_height)

total_height = 0
for height in student_heights:
  total_height += height
  
print(total_height)

student_number = 0
for student in student_heights:
  student_number += 1

print(student_number)

average = round(total_height / student_number)

print (average)
