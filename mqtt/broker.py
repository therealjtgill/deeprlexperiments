import sys
import paho.mqtt.client as mqtt

def on_message(client, userdata, message):
   msg_data = message.payload.decode()
   print("Received message:", msg_data)
   if msg_data == "send":
      client.publish("thisismytopic", payload="message sent from broker", qos=0, retain=False)
   return

def main(argv):
   broker_url = argv[1]
   broker_port = 1883
   client = mqtt.Client()
   client.connect(broker_url, broker_port)
   client.subscribe("thisismytopic", qos=1)
   client.on_message = on_message

   client.loop_forever()

if __name__ == "__main__":
   main(sys.argv)