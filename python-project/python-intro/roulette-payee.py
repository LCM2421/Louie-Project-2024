# Import the random module here
import random
# Split string method
names_string = input("Give me everybody's names, separated by a comma. ")
names = names_string.split(", ")
# 🚨 Don't change the code above 👆

#Write your code below this line 👇
rand_pic = len(names)
rand_choose = random.randint(0, rand_pic - 1)
payer = names[rand_choose]
print(payer, "is going to buy the meal today!")
