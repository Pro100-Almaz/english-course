# english-course
This project aimed to provide small businesses a chatbot with basic functionality

Channel creation 
To channel creation to work you will need to get api-id and api-hash of telegram app 
You’ll get your API ID and API Hash by registering an application on Telegram’s developer site:
- Go to https://my.telegram.org and log in with the same phone number you use in your Telegram app.
- Click API Development Tools.
- Under ‘Create new application’, fill in:
- App title (anything you like)
- Short name (a simple identifier)
- URL (you can enter http://localhost if you don’t have one)
- Submit the form, and you’ll immediately see your App api_id and App api_hash listed.

API ID is a small integer (e.g. 123456).
API Hash is a 32-character hex string (e.g. a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6).

Then you need to save api-id and api-hash to .env file as "APP-API-ID" and "APP-API-HASH" respectively
