from functools import reduce
import json
import multiprocessing
import paho.mqtt.client as mqtt
from server_work_def import ServerWorkDef
import sys
import time
import utils

class Server(object):
   def __init__(self, client_config, client_queues, debug=False):
      self.config = client_config
      self.queues = utils.named_thing(client_queues)

      self.client = mqtt.Client()
      self.client.on_message = self.on_message
      self.client.on_connect = self.on_connect

      self.client.connect(self.config.broker_url, self.config.broker_port)

      for topic in self.config.topics:
         self.client.subscribe(topic.name, qos=1)

      self.listen_topics = [
         e.name for e in self.config.topics if e.action == "listen"
      ]
      print("listen topics:", self.listen_topics)
      self.publish_topic = [
         e.name for e in self.config.topics if e.action == "publish"
      ][0]

   def on_connect(self, client, userdata, flags, rc):
      print("\nPublishing connection message")

   def on_message(self, client, userdata, message):
      #print("Server received a message:", message.topic, message.payload)
      if str(message.topic) not in self.listen_topics:
         return

      decoded_message = str(message.payload.decode("utf-8", "ignore"))
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

def manager_process(manager_client, worker_msg_queue, reg_queue, trainer_queue):
   # UIDs of workers in the current active work session.
   current_worker_uids   = manager_client.config.worker_uids
   # Full configs of workers to include in the next work session.
   next_worker_uids      = []
   # Parameters of work that has been completed, one for each worker.
   completed_work        = []
   # UIDs of workers who have completed work.
   completed_worker_uids = []
   session_uids          = []

   current_work_completed = False
   while True:
      while not worker_msg_queue.empty():
         try:
            worker_str = worker_msg_queue.get().replace("\\", "")[1:-1]
            worker_data = json.loads(
               worker_str, object_hook=utils.named_thing
            )
            completed_work.append(
               worker_data
            )
         except Exception as e:
            print("Couldn't decode string, might not be JSON.")
            print(worker_str)
            print("Error:", str(e))
      
      new_data_available = False
      if len(completed_work) > 0:
         session_uids = sorted([c.session_uid for c in completed_work])
         # Reduce the session uids into a dictionary of counts.
         session_uid_counts = reduce(count_unique_things, session_uids, {})
         # Need to verify that all of the current work falls under the same
         # session UID.
         #do some stuff here...
         completed_worker_uids = [c.worker_uid for c in completed_work]
         if set(completed_worker_uids) == set(current_worker_uids):
            print("All workers in", completed_worker_uids, "have finished.")
            new_data_available = True

      new_workers = []
      while not reg_queue.empty():
         new_worker_config = None
         try:
            new_worker_config_json = reg_queue.get().replace("\\", "")[1:-1]
            new_worker_config = json.loads(
               new_worker_config_json,
               object_hook=utils.named_thing
            )
            print("json type:", type(new_worker_config_json), "\n", new_worker_config_json)
            print(type(json.loads(new_worker_config_json)))

         except Exception as e:
            print("Couldn't decode string into JSON format.")
            print(new_worker_config_json)
            print(str(e))

         print("\nFound a new worker:", new_worker_config, "\nwith type:\n", type(new_worker_config))
         
         if new_worker_config is not None:
            new_workers.append(
               new_worker_config
            )
         time.sleep(2)

      if len(new_workers) > 0:
         print("\nThe entire thing of new workers:\n", new_workers)
         print("type of the element in the new workers list is:\n", type(new_workers[0]))
         new_worker_uids = [w.worker_uid for w in new_workers]
         next_worker_uids = list(
            set(
               current_worker_uids + new_worker_uids
            )
         )
         new_workers = []

      if len(next_worker_uids) > 0:
         #next_worker_uids = [w.worker_uid for w in next_workers]
         if session_uids is None:
            session_uids = [utils.today_string]
         trainer_config_dict = {
            "worker_uids": next_worker_uids,
            "data": [c.data_location for c in completed_worker_uids],
            #"network_uid": session_uids[0]
         }

         trainer_config_str = json.dumps(trainer_config_dict)
         trainer_config = json.loads(trainer_config_str, object_hook=utils.named_thing)
         trainer_queue.put(trainer_config)

def mqtt_process(manager_client):
   print("Started mqtt process") 
   manager_client.run_de_loop()

# Maybe the environment will be part of the model?
# Need to specify how SAR data is saved in trainer function arguments.
def trainer_process(manager_client, trainer_queue, model, environment):
   train_config = None
   current_work = ServerWorkDef(manager_client.config)
   work_output  = None
   while True:
      if not trainer_queue.empty():
         train_config = trainer_queue.get()
      
      if train_config is not None:
         print("Starting work definition with this training config:")
         print(train_config)
         # Run server work definition on received data.
         work_output = current_work.do_work(train_config)
      
      # Only publish the output of the work if the work def returns something.
      if work_output is not None:
         manager_client.publish(json.dumps(work_output))
         work_output = None

      time.sleep(2)

def spinup_server(manager_config):
   reg_queue          = multiprocessing.SimpleQueue()
   worker_msg_queue   = multiprocessing.SimpleQueue()
   trainer_queue      = multiprocessing.SimpleQueue()

   manager_client = Server(
      manager_config,
      {
         "register": reg_queue,
         "worker": worker_msg_queue,
         "trainer": trainer_queue
      }
   )

   p1 = multiprocessing.Process(
      target=mqtt_process,
      args=(
         manager_client,
      )
   )

   p2 = multiprocessing.Process(
      target=manager_process,
      args=(
         manager_client, worker_msg_queue, reg_queue, trainer_queue
      )
   )

   p3 = multiprocessing.Process(
      target=trainer_process,
      args=(
         # manager_client, model, environment
         manager_client, trainer_queue, None, None
      )
   )

   jobs = [p1, p2, p3]
   for j in jobs:
      j.start()

def main(argv):
   test_config_dict = {
     "worker_uids": [],
     "num_rollouts": 50,
     "database_name": "XPDB",
     "ftp": "None",
     "broker_url": "192.168.1.4",
     "broker_port": 1883,
     "topics": [
         {
            "name": "manager",
            "action": "publish"
         },
         {
            "name": "worker",
            "action": "listen"
         },
         {
            "name": "register",
            "action": "listen"
         }
     ],
     "sql_hostname": "192.168.1.4",
     "sql_username": "manager",
     "sql_key_loc": "sqlkey.txt",
     "sql_dbname": "XPDB"
   }

   test_config_json = json.dumps(test_config_dict)

   print("test_config_json:\n", test_config_json)
   test_config = json.loads(test_config_json, object_hook=utils.named_thing)
   spinup_server(test_config)

if __name__ == "__main__":
   main(sys.argv)
