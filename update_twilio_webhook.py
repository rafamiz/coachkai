from twilio.rest import Client

ACCOUNT_SID = 'ACaa11a4f4b4b3c813d73489ccb64c5f8c'
AUTH_TOKEN = 'AYRKGJE5KXWC8CY31VNBHK7U'
NEW_WEBHOOK = 'https://coachkai-production.up.railway.app/webhook'

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# Update WhatsApp sandbox webhook
sandbox = client.messaging.v1.services.list()
print("Services:", sandbox)

# Try updating via phone number resource
incoming = client.incoming_phone_numbers.list()
for n in incoming:
    print(n.phone_number, n.sms_url)
