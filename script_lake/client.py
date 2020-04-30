from client_work_def import ClientWorkDef
import json
import multiprocessing
import os
import paho.mqtt.client as mqtt
import sys
import time
import utils

class Client(object):
   def __init__(self, client_config, client_queue, debug=False):
      self.config = client_config
      self.queue = client_queue

      self.worker_uid = client_config.worker_uid

      self.client = mqtt.Client()
      self.client.on_message = self.on_message
      self.client.on_connect = self.on_connect

      self.client.connect(self.config.broker_url, self.config.broker_port)

      for topic in self.config.topics:
         self.client.subscribe(topic.name, qos=1)

      self.listen_topics = [
         e.name for e in self.config.topics if e.action == "listen"
      ]

      self.register_topic = [
         e.name for e in self.config.topics if e.action == "register"
      ][0]

      self.publish_topic = [
         e.name for e in self.config.topics if e.action == "publish"
      ][0]

      registration_info_dict = {
         "worker_uid": self.worker_uid
      }

      self.registration_info = utils.to_named_thing(registration_info_dict)

   def on_connect(self, client, userdata, flags, rc):
      print("\nPublishing connection message")
      self.register()

   def on_message(self, client, userdata, message):
      if not message.topic in self.listen_topics:
         print("message topic:", message.topic, "not in listen topics:", self.listen_topics)
         return

      decoded_message = message.payload.decode("utf-8")
      print("\nReceived message", decoded_message, message.topic)
      self.queue.put(decoded_message)

   def publish(self, message):
      self.client.publish(
         self.publish_topic,
         message
      )

   def register(self):
      self.client.publish(
         self.register_topic,
         payload=str(self.registration_info).encode(),
         qos=1,
         retain=False
      )

   def run_de_loop(self):
      self.client.loop_forever()

def mqtt_process(worker_client):
   print("Started mqtt process")
   worker_client.run_de_loop()

def work_process(work_queue, worker_client):
   print("Started work process")
   current_work = ClientWorkDef(worker_client.config)
   worker_uid = worker_client.config.worker_uid
   while True:

      new_work = utils.extract_json_from_queue(work_queue)
      if len(new_work) > 0:
         new_work = new_work[-1]
         if worker_uid in new_work.worker_uids:
            print("Doing work:\n", new_work)
            response = current_work.do_work(new_work)

            if response is not None:
               worker_client.publish(json.dumps(response))
            else:
               print("Client worker returned a blank response, not sending to server.")

         else:
            print("Worker UID", worker_uid, "not mentioned in current work.")
            # worker_client.publish(
            #    str(worker_client.registration_info).encode()
            # )
            worker_client.register()

      time.sleep(2)
      print("looping work")

def spinup_worker(worker_config):
   work_queue = multiprocessing.SimpleQueue()
   worker_mqtt = Client(worker_config, work_queue)

   p1 = multiprocessing.Process(
      target=mqtt_process,
      args=(
         worker_mqtt,
      )
   )

   p2 = multiprocessing.Process(
      target=work_process,
      args=(
         work_queue,
         worker_mqtt
      )
   )

   jobs = [p1, p2]

   for j in jobs:
      j.start()

def main(argv):
   config_dict = {
      "broker_url": "192.168.1.4",
      "broker_port": 1883,
      "topics": [
         {
            "name": "manager",
            "action": "listen"
         },
         {
            "name": "worker",
            "action": "publish"
         },
         {
            "name": "register",
            "action": "register"
         }
      ],
      "worker_uid": 1,
      "sql_hostname": "192.168.1.4",
      "sql_username": "worker",
      "sql_key_loc": "sqlkey.txt",
      "sql_dbname": "XPDB"
   }

   if len(argv) > 1:
      config_filename = argv[1]
      if os.path.exists(config_filename):
         config_file = open(config_filename, "r")
         config_json = "".join(config_file.readlines())
         config_dict = json.loads(config_json, parse_int=int, parse_float=float)
         config_dict["worker_uid"] = int(config_dict["worker_uid"])
         config_dict["broker_port"] = int(config_dict["broker_port"])
         print("Using config dict from disk,", argv[1])

   config = utils.to_named_thing(config_dict)

   #print(json.loads(str(config)))

   spinup_worker(config)
   print("exiting main loop")

if __name__ == "__main__":
   main(sys.argv)
