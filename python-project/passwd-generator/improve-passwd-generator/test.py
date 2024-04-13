try:
    file = open("a_file.txt")
    a_dictionary = {"key": "value"}
    print(a_dictionary["key"])
except FileNotFoundError:
    file = open("a_file.txt", "w")
    file.write("Something")
except KeyError as error_message:
    print(f"The key {error_message} doesn't exist.")
else:
    content = file.read()
    print(content)
finally:
    file.close()
    print("File was closed.")
