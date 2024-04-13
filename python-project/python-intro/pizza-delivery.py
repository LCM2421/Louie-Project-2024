# 🚨 Don't change the code below 👇
print("Welcome to Python Pizza Deliveries!")
size = input("What size pizza do you want? S, M, or L ")
pepperoni = input("Do you want pepperoni? Y or N ")
extra_cheese = input("Do you want extra cheese? Y or N ")
# 🚨 Don't change the code above 👆

#Write your code below this line 👇
bill = 0
if size == "S":
  bill += 15
  if extra_cheese == "Y":
    bill +=1
  if pepperoni == "Y":
    if size == "S":
      bill += 2
    else:
      bill += 3
elif size == "M":
  bill += 20
  if extra_cheese == "Y":
    bill +=1
  if pepperoni == "Y":
    if size == "S":
      bill += 2
    else:
      bill += 3
elif size == "L":
  bill += 25
  if extra_cheese == "Y":
    bill +=1
  if pepperoni == "Y":
    if size == "S":
      bill += 2
    else:
      bill += 3
else:
  print("Incorrect please type the correct capital letter")

if bill >= 1:
  print(f"Your Final bill is ${bill}.")
