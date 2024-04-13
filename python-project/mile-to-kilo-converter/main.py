from tkinter import *


#Button
def button_clicked():
    button_click = "Button got clicked"
    new_text = input.get()
    my_label.config(text=new_text)

window = Tk()
window.title("My fisrt GUI Program")
window.minsize(width=500, height=300)
window.config(padx=100, pady=200)

#Label
my_label = Label(text="I am a Label", font=("Arial", 24, "normal"))
my_label["text"] = "New Text"
my_label.config(text="New Text")
my_label.grid(column=0, row=0)
my_label.config(padx=50, pady=50)

button = Button(text="Click Me!", command=button_clicked)
# button.pack()
button.grid(column=1, row=1)

button2 = Button(text="New Button")
button2.grid(column=2, row=0)

#Entry
input = Entry(width=10)
# input.pack()
input.grid(column=3, row=2)
print(input.get())



#loop the mainloop py
window.mainloop()
