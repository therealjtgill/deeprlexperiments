import sys
import paho.mqtt.client as mqtt

def on_message(client, userdata, message):
   print("Received message:", message.payload.decode())
   return

def main(argv):
   broker_url = "192.168.1.4"
   broker_port = 1883
   client = mqtt.Client()
   client.connect(broker_url, broker_port)
   client.subscribe("thisismytopic", qos=1)
   client.on_message = on_message

   client.loop_forever()

if __name__ == "__main__":
   main(sys.argv)