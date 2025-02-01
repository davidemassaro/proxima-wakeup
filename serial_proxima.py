import argparse
import serial
import logging, os,time
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request
import uvicorn
from datetime import datetime
import socket

com = "COM6"
debug = True
send_mode = "tcp"  # tcp or serial

def main():
    global com, debug, send_mode  # Declare global variables to update them
    
    parser = argparse.ArgumentParser(description="Proxima Serial Emulator Script")
    parser.add_argument("--com", type=str, default=com, help="COM1 or /dev/ttyUSB0 port to use")
    parser.add_argument("--send_mode", type=str, choices=["tcp", "serial"], default=send_mode, help="Send mode (tcp or serial)")
    parser.add_argument("--no-debug", action="store_true", help="Enable debug mode", default=True)

    args = parser.parse_args()

    # Update configuration based on arguments
    com = args.com
    debug = args.debug
    send_mode = args.send_mode

    # Your main code logic here
    print(f"Using COM port: {com}")
    print(f"Debug mode: {debug}")
    print(f"Send mode: {send_mode}")

app = FastAPI()

log_path = os.path.join(os.getcwd(), "log_serial.log")

# Configure logging with rotation
log_handler = RotatingFileHandler(
    log_path, maxBytes=1 * 1024 * 1024 * 1024, backupCount=5
)
log_handler.setLevel(logging.INFO)
log_formatter = logging.Formatter(
    "%(asctime)s;%(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
log_handler.setFormatter(log_formatter)

# Console handler for terminal output
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(log_formatter)

# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)
logger.addHandler(console_handler)



# Configurazione del dispositivo Moxa
MOXA_IP = "192.168.127.254"
MOXA_PORT = 4001


def send_string_moxa(command):
    ip=MOXA_IP
    port=MOXA_PORT
    try:
        # Crea un socket TCP
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        # Connessione al dispositivo Moxa
        s.connect((ip, port))
        # Invia il comando
        s.sendall(command.encode())
        # Ricevi la risposta
        #response = s.recv(1024)
        # Chiudi la connessione
        s.close()
    except Exception as e:
        logger.warning(f"Failed to communicate with Moxa: {e}")
        return None

"""
ROOM STATUS IDs:
1 SPORCA OCCUPATA
2 SPORCA LIBERA
3 PULITA OCC
4 PULITA LIB
5 ISPEZIONATA OCCUPATA
6 ISPEZIONATA LIBERA
"""

def invia_dati(data):
    # Configura la porta COM
    ser = serial.Serial(
        com,
        baudrate=9600,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=1,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
        writeTimeout=2,
    )
    try:
        if ser.isOpen():
            ser.close()
        ser.open()
        # Invia la stringa
        ser.write(data.encode())
        logger.info("Serial data sent successfully")
    except serial.SerialException as e:
        print(f"Failed to send serial data: {e}")
        logger.error(f"Failed to send serial data: {e}")
    finally:
        # Chiudi la connessione
        ser.close()
        time.sleep(0.5)
        logger.info("Serial closed successfully")


def genera_stringa_stato_stanza(anno, mese, giorno, ora, minuti, numero_stanza, stato):
    # Inizializza la stringa con spazi vuoti per 62 caratteri (posizione massima)
    data = [" "] * 62

    # Inserisci i dati nei rispettivi campi (considerando l'indice base 0)
    data[19:22] = list(f"{numero_stanza:>3}")  # Numero stanza in pos 20-22
    data[42] = stato  # Stato stanza in pos 43
    data[61] = "s"  # Valore predefinito di "n.r.right" in pos 62

    # Inserisci i dati per giorno/ora stato camera avanzato
    data[7:9] = list(f"{anno:>2}")  # Anno in pos 8-9
    data[9:11] = list(f"{mese:>2}")  # Mese in pos 10-11
    data[11:13] = list(f"{giorno:>2}")  # Giorno in pos 12-13
    data[14:16] = list(f"{ora:>2}")  # Ora in pos 15-16
    data[16:18] = list(f"{minuti:>2}")  # Minuti in pos 17-18

    stringa_completa = "".join(data)
    logger.info(f"Sending room status data via {send_mode}")
    logger.info(stringa_completa)
    if send_mode=="tcp":
        send_string_moxa(stringa_completa)
    elif send_mode=="serial":
        invia_dati(stringa_completa)
    return stringa_completa


def genera_stringa_addebiti(
    anno,
    mese,
    giorno,
    ora,
    minuti,
    interno_chiamante,
    numero_chiamato,
    durata_ore,
    durata_minuti,
    durata_secondi,
    identificativo="a",
):

    # Inizializza la stringa con spazi vuoti per 62 caratteri (posizione massima)
    data = [" "] * 62

    # Inserisci i dati nei rispettivi campi (considerando l'indice base 0)
    data[7:9] = list(f"{anno:02d}")  # Anno in pos 8-9
    data[9:11] = list(f"{mese:02d}")  # Mese in pos 10-11
    data[11:13] = list(f"{giorno:02d}")  # Giorno in pos 12-13
    data[14:16] = list(f"{ora:02d}")  # Ora in pos 15-16
    data[16:18] = list(f"{minuti:02d}")  # Minuti in pos 17-18
    data[19:22] = list(f"{interno_chiamante:>3}")  # Interno chiamante in pos 20-22
    data[24] = f"{durata_ore}"  # Durata ore in pos 25
    data[25:27] = list(f"{durata_minuti:02d}")  # Durata minuti in pos 26-27
    data[27:29] = list(f"{durata_secondi:02d}")  # Durata secondi in pos 28-29
    data[40:54] = list(f"{numero_chiamato:<14}")  # Numero chiamato in pos 41-54
    data[61] = identificativo  # Identificativo in pos 62

    stringa_completa = "".join(data) + chr(
        13
    )  # Aggiunge il carattere ASCII 13 (fine record)
    logger.info(f"Sending addebiti data via {send_mode}")
    logger.info(stringa_completa)
    if send_mode=="tcp":
        send_string_moxa(stringa_completa)
    elif send_mode=="serial":
        invia_dati(stringa_completa)
    # Converti la lista in una stringa
    return stringa_completa


@app.post("/room-status")
async def roomstatus_webhook(request: Request):
    # Ricevi e stampa il corpo della richiesta
    body = await request.json()
    print("\n=== Received Webhook ===")
    print("Headers:", dict(request.headers))
    print("Body:", body)
    print("=======================\n")
    # Estrai i dati dal corpo della richiesta
    numero_stanza = body.get("room")
    stato = body.get("status")

    now = datetime.now()
    anno = now.year % 100  # Ultime due cifre dell'anno
    mese = now.month
    giorno = now.day
    ora = now.hour
    minuti = now.minute

    # Genera la stringa di stato della stanza
    stringa_stato = genera_stringa_stato_stanza(
        anno, mese, giorno, ora, minuti, numero_stanza, stato
    )
    # Stampa la stringa generata
    print("Generated String:", stringa_stato)
    return {"status": "success", "message": "Webhook received"}


@app.post("/bill-call")
async def billcall_webhook(request: Request):
    # Ricevi e stampa il corpo della richiesta
    body = await request.json()
    print("\n=== Received Webhook ===")
    print("Headers:", dict(request.headers))
    print("Body:", body)
    print("=======================\n\n")

    # Estrai i dati dal corpo della richiesta
    numero_stanza = body.get("room")
    stato = body.get("status")
    call_destination = stato.get("call_destination")
    call_duration_seconds = stato.get("call_duration_seconds")
    call_duration_formatted = stato.get("call_duration_formatted")
    service_class_code = stato.get("service_class_code")
    service_class_name = stato.get("service_class_name")

    # Converti la durata della chiamata in ore, minuti e secondi
    durata_ore, durata_minuti, durata_secondi = map(
        int, call_duration_formatted.split(":")
    )

    now = datetime.now()
    anno = now.year % 100  # Ultime due cifre dell'anno
    mese = now.month
    giorno = now.day
    ora = now.hour
    minuti = now.minute

    # Genera la stringa di addebiti
    genera_stringa_addebiti(
        anno,
        mese,
        giorno,
        ora,
        minuti,
        numero_stanza,
        call_destination,
        durata_ore,
        durata_minuti,
        durata_secondi,
    )
    return {"status": "success", "message": "Webhook received"}

if __name__ == "__main__":
    main()
    # Esempio di utilizzo
    if debug:
        now = datetime.now()
        anno = now.year % 100  # Ultime due cifre dell'anno
        mese = now.month
        giorno = now.day
        ora = now.hour
        minuti = now.minute
        genera_stringa_addebiti(
            anno,
            mese,
            giorno,
            ora,
            minuti,
            interno_chiamante="360",
            numero_chiamato="3404582108",
            durata_ore=0,
            durata_minuti=5,
            durata_secondi=30,
        )
        genera_stringa_stato_stanza(
            anno, mese, giorno, ora, minuti, numero_stanza="360", stato="9"
        )
        
    else:
        uvicorn.run(app, host="0.0.0.0", port=80)

"""
curl -X POST http://127.0.0.1/bill-call -H "Content-Type: application/json" -d "{\"room\": \"360\", \"status\": { \"call_destination\": \"0458403665\", \"call_duration_seconds\": \"000012\", \"call_duration_formatted\": \"01:10:12\", \"service_class_code\": \"N\", \"service_class_name\": \"National\"}}"
curl -X POST http://127.0.0.1/room-status -H "Content-Type: application/json" -d "{\"room\": \"360\", \"status\": \"9\"}"
"""
