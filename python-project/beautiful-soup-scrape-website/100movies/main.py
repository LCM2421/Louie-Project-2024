import requests
from bs4 import BeautifulSoup

URL = "https://web.archive.org/web/20200518073855/https://www.empireonline.com/movies/features/best-movies-2/"
response = requests.get(URL)
# Write your code below this line 👇
top_100_movies = response.text

soup = BeautifulSoup(top_100_movies, "html.parser")

all_movies = soup.find_all(name="h3", class_="title")

movie_title = [movie.getText() for movie in all_movies]
movies = movie_title[::-1]
print(movies)

with open("movies.txt", mode="w", encoding="utf-8") as file:
    for movie in movies:
        file.write(f"{movie}\n")



