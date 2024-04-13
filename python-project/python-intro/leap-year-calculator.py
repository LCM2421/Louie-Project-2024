# 🚨 Don't change the code below 👇
year = float(input("Which year do you want to check? "))
# 🚨 Don't change the code above 👆

#Write your code below this line 👇
if year % 400 == 0:
  if year % 100 == 0:
    if year % 4 == 0:
      print("Leap Year.")
    else:
      print("Not leap year.")
else:
  print("Not Leap")

# The below is more accurate on the above codes.
# if (year % 400 == 0) and (year % 100 == 0):
#     print("{0} is a leap year".format(year))

# elif (year % 4 ==0) and (year % 100 != 0):
#     print("{0} is a leap year".format(year))

# else:
#     print("{0} is not a leap year".format(year))
