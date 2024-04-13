from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By

URL = "https://www.saucedemo.com/"
chrome_options = webdriver.ChromeOptions()
chrome_options.add_experimental_option("detach", True)

driver = webdriver.Chrome(options=chrome_options)
driver.get(URL)

# article_count = driver.find_elements(By.LINK_TEXT, value="6,719,927") # use to list the text
# article = driver.find_element(By.LINK_TEXT, value="6,719,927") # use to interact a website
# # article.click()
#
# search = driver.find_element(By.NAME, value="search")
# search.send_keys("Python")
# search.send_keys(Keys.ENTER)

username = driver.find_element(By.NAME, value="user-name")
username.send_keys("standard_user")

password = driver.find_element(By.NAME, value="password")
password.send_keys("secret_sauce")

submit = driver.find_element(By.NAME, value="login-button")
submit.send_keys(Keys.ENTER)

# driver.quit()
