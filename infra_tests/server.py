import sys
import time
import paho.mqtt.client as mqtt
import json

def on_message(client, userdata, message):
   msg_data = message.payload.decode()
   if message.topic == "manager":
      return
#   print("Received message:", msg_data)
   time.sleep(2)
   stuff_to_do = {
      "task_uid": 10,
      "time": time.time(),
      "worker_uids": [1]
   }

   print("Stuff to do:", stuff_to_do)

   client.publish(
      "manager",
      payload=json.dumps(stuff_to_do),
      qos=0,
      retain=False
   )
   return

def main(argv):
   broker_url = argv[1]
   broker_port = 1883
   client = mqtt.Client()
   client.connect(broker_url, broker_port)
   client.subscribe("worker", qos=1)
   client.subscribe("manager", qos=1)
   client.on_message = on_message

   stuff_to_do = {
      "task_uid": 10,
      "time": time.time(),
      "worker_uids": [1]
   }
   client.publish("manager", json.dumps(stuff_to_do))

   client.loop_forever()

if __name__ == "__main__":
   main(sys.argv)
