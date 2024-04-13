import random
from art import logo, vs
from replit import clear
from game_data import data

# Format account data into printable format.
def format_data(data):
  """Format the account data into printable format."""
  acc_name = data["name"]
  acc_desc = data["description"]
  acc_country = data["country"]
  return f"{acc_name}, a {acc_desc}, from {acc_country}"

## If Statement
def check_answer(guess, a_followers, b_followers):
  """Take the user guess and follower counts and returns if they got it right."""
  if a_followers > b_followers:
    return guess == "a"
  else:
    return guess == "b"

# Display the art
print(logo)
score = 0
game_should_continue = True
ran_acc_b = random.choice(data)

# Make game repeatable.
while game_should_continue:
  # Generate a random account from the game data.

  # Make B become the next A.
  ran_acc_a = ran_acc_b
  ran_acc_b = random.choice(data)
  while ran_acc_a == ran_acc_b:
    ran_acc_b = random.choice(data)

  print(f"Compare A: {format_data(ran_acc_a)}.")
  print(vs)
  print(f"Compare B: {format_data(ran_acc_b)}.")

  # Ask user for a guess.
  guess = input("Who has more followers? Type 'A' or 'B': ").lower()

  # Check if user is correct.
  ## Get follower count.

  a_follower_count = ran_acc_a["follower_count"]
  b_follower_count = ran_acc_b["follower_count"]
  is_correct = check_answer(guess, a_follower_count, b_follower_count)

  # Clear screen between rounds.
  clear()
  print(logo)
  # Feedback.
  # Score Keeping.
  if is_correct:
    score += 1
    print(f"You're right! Current score: {score}.")
  else:
    game_should_continue = False
    print(f"Sorry, that's wrong. Final score: {score}.")
