import requests
from datetime import datetime, timedelta
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import logging
from logging.handlers import RotatingFileHandler
log_path = os.path.join(os.getcwd(), 'log.log')

# Configure logging with rotation
log_handler = RotatingFileHandler(log_path, maxBytes=1*1024*1024*1024, backupCount=5)
log_handler.setLevel(logging.INFO)
log_formatter = logging.Formatter('%(asctime)s;%(message)s', datefmt='%Y-%m-%d %H:%M:%S')
log_handler.setFormatter(log_formatter)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

po_extension = "360"

def log_message(message):
    logger.info(message)

def sendmail(subject, body):
    from_addr = "redacted@example.com"
    to_addr = "redacted@example.com"
    # Create the email message
    msg = MIMEMultipart()
    msg['From'] = from_addr
    msg['To'] = to_addr
    msg['Cc'] = "redacted@example.com"
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))
    

    smtp_server="smtp.example.com"
    smtp_port=25
    # Send the email
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        #server.login(smtp_user, smtp_password)
        server.sendmail(from_addr, to_addr, msg.as_string())
        server.quit()
        print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {e}")

def sendcall(message,extension):
    current_time = datetime.now()
    url = "https://voip.example.com/api/v2/phone/robot-call"
    username = "api"
    password = "REDACTED_SECRET"
    body = {
        "caller_id_number": "WU-Camera"+extension,
        "number": po_extension,
        "message": "tts:it"+message,
        "timeout": "30"
    }
    response = requests.post(url, json=body, auth=(username, password), verify=False)
    log_message(message=("esito call response "+response.text+" alle ore "+current_time.strftime('%Y-%m-%d %H:%M:%S')))


url = "https://voip.example.com/api/ucpanel/auth/login"
payload = {
    "username": "560",
    "password": "REDACTED_SECRET"
}

response = requests.post(url, json=payload, verify=False)

def check_and_save_wakeup_uuid(wakeup_uuid, file_path='wakeup_uuids.txt'):
    # Check if the wakeup_uuid exists in the file
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            uuids = file.read().splitlines()
            if wakeup_uuid in uuids:
                return False

    # Save the wakeup_uuid to the file
    with open(file_path, 'a') as file:
        file.write(wakeup_uuid + '\n')
    return True


if response.status_code == 200:
    print("Login successful")
    token = response.json().get('token')
    
    # Use the token to make a request to the rooms endpoint
    rooms_url = f"https://voip.example.com/api/ucpanel/hotel/rooms?token={token}"
    rooms_response = requests.get(rooms_url, verify=False)
    
    if rooms_response.status_code == 200:
        print("Rooms data retrieved successfully")
        rooms_data = rooms_response.json()
        # Extract and print only the wakeups part
        wakeups = []
        for room in rooms_data.get('data', []):
            booking = room.get('booking', {})
            
            wakeups.extend(booking.get('wakeups', []))

        # Check if the wakeup call has expired and if answered_at is not None
        current_time = datetime.now()
        print(f"Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        for wakeup in wakeups:
            timeout = datetime.strptime(wakeup['timeout'], '%Y-%m-%d %H:%M:%S')
            answered_at = wakeup['answered_at']
            
            if current_time > timeout and answered_at is not None:
                if check_and_save_wakeup_uuid(wakeup['wakeup_uuid']):
                    voice_message=f"La sveglia per la camera {wakeup['extension']} è scaduta e il cliente ha risposto alle ore: {wakeup['answered_at']}"
                    message=f"SENDMAIL - Wakeup call {wakeup['wakeup_uuid']} for ext {wakeup['extension']} has expired and was answered at {answered_at}"
                    log_message(message=message)
                    sendcall(voice_message,wakeup['extension'])
                    sendmail(
                        subject=f"Sveglia camera {wakeup['extension']}",body=f"Il cliente nella camera {wakeup['extension']} ha risposto alla sveglia alle ore: {wakeup['answered_at']}")
                else:
                    message=f"Wakeup call {wakeup['wakeup_uuid']} for ext {wakeup['extension']} has expired and was answered at {answered_at}"
                    log_message(message=message)

            elif current_time > timeout:
                if check_and_save_wakeup_uuid(wakeup['wakeup_uuid']):
                    voice_message=f"La sveglia per la camera {wakeup['extension']} è scaduta e non è stata risposta"
                    message=f"SENDMAIL - Wakeup call {wakeup['wakeup_uuid']} for ext {wakeup['extension']} has expired and was not answered"
                    log_message(message=message)
                    sendcall(voice_message,wakeup['extension'])
                    sendmail(
                        subject=f"Sveglia camera {wakeup['extension']}",body=f"Il cliente nella camera {wakeup['extension']} non ha risposto alla sveglia impostata alle: {wakeup['timeout']}")
                else:
                    message=f"Wakeup call {wakeup['wakeup_uuid']} for ext {wakeup['extension']} has expired and was not answered"
                    log_message(message=message)
            else:
                message=f"Wakeup call {wakeup['wakeup_uuid']} for ext {wakeup['extension']} is still pending"
                log_message(message=message)
    else:
        log_message(message="Failed to retrieve rooms data")
        log_message(message=f"Status code: {rooms_response.status_code}")
        log_message(message=f"Response: {rooms_response.text}")
else:
    log_message(message="Login failed")
    log_message(message=f"Status code: {response.status_code}")
    log_message(message=f"Response: {response.text}")
