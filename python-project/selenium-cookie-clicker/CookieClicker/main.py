from selenium import webdriver
from selenium.webdriver.common.by import By
import selenium

# Keep Chrome browser open after program finishes
chrome_options = webdriver.ChromeOptions()
chrome_options.add_experimental_option("detach", True)

# URL = ("https://www.amazon.com/JOMISE-Enhanced-G-Sensor-Assistance-Recording/dp/B09288CFDR/ref=sr_1_27_sspa?crid="
#        "OOJTVIZ2K5TQ&keywords=gadget&qid=1695709155&sprefix=gadge%2Caps%2C304&sr=8-27-spons&sp_csd="
#        "d2lkZ2V0TmFtZT1zcF9tdGY&psc=1")

URL = ("https://www.python.org/")

driver = webdriver.Chrome(options=chrome_options)
driver.get(URL)

# price_dollar = driver.find_element(By.CLASS_NAME, value="a-price-whole")
# price_cents = driver.find_element(By.CLASS_NAME, value="a-price-fraction")
# print(f"The price dollar {price_dollar.text}.{price_cents.text}")


event_times = driver.find_elements(By.CSS_SELECTOR, value=".event-widget time")
event_names = driver.find_elements(By.CSS_SELECTOR, value=".event-widget li a")
events = {}

for n in range(len(event_times)):
    events[n] = {
        "time": event_times[n].text,
        "name": event_names[n].text,
    }

print(events)


# for time in event_times:
#     print(time.text)

# driver.close() # close single tab
driver.quit()  # quit the entire browser
