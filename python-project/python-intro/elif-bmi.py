# 🚨 Don't change the code below 👇
height = float(input("enter your height in m: "))
weight = float(input("enter your weight in kg: "))
# 🚨 Don't change the code above 👆

#Write your code below this line 👇
bmi = round(weight / height ** 2)
if bmi < 18.5:
  print(f"Your BMI is {bmi}, you are \033[1munderweight.\033[0m")
elif bmi < 25:
  print(f"Your BMI is {bmi}, you are \033[1mnormal weight.\033[0m")
elif bmi < 30:
  print(f"Your BMI is {bmi}, you are \033[1mslightly overweight.\033[0m")
elif bmi < 35:
  print(f"Your BMI is {bmi}, you are \033[1mobese.\033[0m")
else:
  print(f"Your BMI is {bmi}, you are \033[1mclinically obese.\033[0m")
