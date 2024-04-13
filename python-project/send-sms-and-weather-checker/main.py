import requests
from twilio.rest import Client

OWM_Endpoint = "https://api.openweathermap.org/data/3.0/onecall"
api_key = "<YOUR_API_KEY>"
account_sid = "<YOUR_SID_ACCOUNT>"
auth_token = "<YOUR_AUTH_TOKEN>"

weather_params = {
    "lat": 14.554729,
    "lot": 121.024445,
    "appid": api_key,
    "exclude": "current,minutely,daily"
}

response = requests.get(OWM_Endpoint, params=weather_params)
response.raise_for_status()
weather_data = response.json()
weather_slice = weather_data["hourly"][:12]

will_rain = False

for hour_data in weather_slice:
    condition_code = hour_data["weather"][0]["id"]
    if int(condition_code) < 700:
        will_rain = True

if will_rain:
    print("Bring an umbrella.")
    client = Client(account_sid, auth_token)

    message = client.messages.create(
        body="Its going to rain today. Remember to bring an umbrella.",
        from_='<THE_SENDER>',
        to='<YOUR_NUMBER>'
    )
print(message.status)
# print(weather_data["hourly"][0]["weather"][0]["id"])


