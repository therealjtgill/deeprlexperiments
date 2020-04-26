from functools import reduce
import json
import multiprocessing
import paho.mqtt.client as mqtt
import sys
import time
import utils

class Server(object):
   def __init__(self, client_config, client_queues, debug=False):
      self.config = client_config
      self.queues = utils.named_thing(client_queue)

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

      self.publish_topic = [
         e.name for e in self.config.topics if e.action == "publish"
      ][0]

   def on_connect(self, client, userdata, flags, rc):
      print("\nPublishing connection message")

   def on_message(self, client, userdata, message):
      if str(message.topic) not in self.listen_topics:
         return

      decoded_message = message.payload.decode("utf-8")
      print("\nReceived message", decoded_message, message.topic)

      if str(message.topic) == "register":
         self.queues.register.put(decoded_message)
      elif str(message.topic) == "worker":
         self.queues.worker.put(decoded_message)

   def publish(self, message):
      self.client.publish(
         self.publish_topic,
         message
      )

   def run_de_loop(self):
      self.client.loop_forever()

def count_unique_things(counts, next_thing):
   if next_thing in counts.keys():
      counts[next_thing] += 1
   else:
      counts[next_thing] = 1
   return counts

def manager_process(manager_client, worker_msg_queue, reg_queue):
   current_workers = manager_client.config.worker_uids
   next_workers    = manager_client.config.worker_uids
   completed_work  = []

   while True:
      
      while not worker_msg_queue.empty():
         completed_work.append(
            json.loads(worker_msg_queue.get(), object_hook=utils.named_thing)
         )
      
      new_data_available = False
      if len(completed_work) > 0:
         session_uids = sorted([c.session_uid for c in completed_work])
         # Reduce the session uids into a dictionary of counts.
         session_uid_counts = reduce(count_unique_things, session_uids, {})
         # Need to verify that all of the current work falls under the same
         # session UID.
         #do some stuff here...
         completed_workers = [c.worker_uid for c in completed_work]
         if set(completed_workers) == set(current_workers):
            print("All workers in", current_workers, "have finished.")
            new_data_available = True

      new_workers = []
      while not reg_queue.empty():
         new_workers.append(
            json.loads(reg_queue.get(), object_hook=utils.named_thing)
         )
         time.sleep(2)

      if len(new_workers) > 0:
         next_workers = list(
            set(
               current_workers + new_workers
            )
         )

      trainer_config = {
         "worker_uids": next_workers,
         "data": [c.data_location for c in completed_workers],
         "network_uid": 
      }

def mqtt_process(manager_client):
   print("Started mqtt process")
   manager_client.run_de_loop()

# Maybe the environment will be part of the model?
# Need to specify how SAR data is saved in trainer function arguments.
def trainer_process(manager_client, model, environment):

   while True:
      pass

def spinup_server(manager_config):
   reg_queue          = multiprocessing.SimpleQueue()
   worker_msg_queue   = multiprocessing.SimpleQueue()
   trainer_queue      = multiprocessing.SimpleQueue()

   manager_client = Server(manager_config)
   jobs = []

   p1 = multiprocessing.Process(
      target=mqtt_process,
      args=(
         manager_client
      )
   )

   p2 = multiprocessing.Process(
      target=manager_process,
      args=(
         manager_client, worker_msg_queue, reg_queue
      )
   )

   p3 = multiprocessing.Process(
      target=trainer_process,
      args=(
         manager_client, model, environment
      )
   )

def main(argv):
   test_config_dict = {
     "worker_uids": [],
     "num_rollouts": 50,
     "database_name": "XPDB",
     "ftp": "None"
   }

if __name__ == "__main__":
   main(sys.argv)
