import random
rock = '''
    _______
---'   ____)
      (_____)
      (_____)
      (____)
---.__(___)
'''

paper = '''
    _______
---'   ____)____
          ______)
          _______)
         _______)
---.__________)
'''

scissors = '''
    _______
---'   ____)____
          ______)
       __________)
      (____)
---.__(___)
'''

#Write your code below this line 👇
game_image = [rock, paper, scissors]

print("Bato-bato pick game")
user_choice = int(input("What do you choose ? \nType 0 for Rock, 1 for Paper or 2 for Scissors.\n"))

if user_choice >= 3 or user_choice < 0:
  print("You Type an invalid number, You Lose!")
else:
  print(game_image[user_choice ])
  
  comp_choose = random.randint(0, 2)
  print("Computer chose:")
  print(game_image[comp_choose])

  if user_choice == 0 and comp_choose == 2:
    print("You Win!")
  elif comp_choose == 0 and user_choice == 2:
    print("You Lose!")
  elif comp_choose > user_choice:
    print("You Lose!!")
  elif user_choice > comp_choose:
    print("You Win!")
  elif comp_choose == user_choice:
    print("Draw! Please try it again!")
