from functools import reduce
import json
import multiprocessing
import paho.mqtt.client as mqtt
from server_work_def import ServerWorkDef, SessionManager
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
      print("publishing a new message:", message, "on topic:", self.publish_topic)
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

def mqtt_process(manager_client):
   print("Started mqtt process") 
   manager_client.run_de_loop()

def manager_process(
   manager_client,
   worker_msg_queue,
   reg_queue,
   trainer_queue,
   session_queue
):
   # UIDs of workers in the current active work session.
   current_worker_uids   = manager_client.config.worker_uids
   # Full configs of workers to include in the next work session.
   next_worker_uids      = []
   # Parameters of work that has been completed, one for each worker.
   completed_work        = []
   # UIDs of workers who have completed work.
   completed_worker_uids = []
   session_uids          = [0]
   current_session = utils.to_named_thing(
      {
         "session_uid": "0",
         "worker_uids": []
      }
   )

   session_manager = SessionManager()
   while True:
      print("Grabbing new workers")
      new_workers = utils.extract_json_from_queue(reg_queue)

      session_manager.add_workers(new_workers)

      if session_manager.session_active:
         print("Session is active, looking for completed work")
         completed_work = utils.extract_json_from_queue(worker_msg_queue)
         if session_manager.attempt_end_session(completed_work):
            # If all work is completed give it to trainer for training.
            trainer_queue.put(str(session_manager.completed_session))
            #session_params = session_manager.start_session()

      print("Grabbing list of new sessions")
      new_sessions = utils.extract_json_from_queue(session_queue)
      print("all worker uids:", session_manager.all_worker_uids)
      if (len(new_sessions) == 0) and (not session_manager.session_active) and (len(session_manager.all_worker_uids) > 0):
         print("Putting something in the trainer queue...")
         session_manager.start_session()
         trainer_queue.put(str(session_manager.current_session))
         
      elif len(new_sessions) > 0:
         print("New sessions are available, making them active")
         # If new work is available for the workers, mark the work as new in
         # the session manager and publish it to the workers.
         session_manager.start_session(new_sessions[-1])
         manager_client.publish(str(new_sessions[-1]))

      time.sleep(2)

# Maybe the environment will be part of the model?
# Need to specify how SAR data is saved in trainer function arguments.
def trainer_process(
   manager_config,
   session_queue,
   trainer_queue,
   model,
   environment
):
   train_config = None
   current_work = ServerWorkDef(manager_config)
   work_output  = None
   while True:
      training_sessions = utils.extract_json_from_queue(trainer_queue)
      if len(training_sessions) > 0:
         print("training session?", training_sessions[-1])
         if training_sessions[-1].session_uid == 0:
            print("Putting together default work for workers", training_sessions[-1].worker_uids)
            work_output = current_work.default_work(training_sessions[-1])
            print("\tDefault work output: ", work_output)
         else:
            work_output = current_work.do_work(training_sessions[-1])

         if work_output is not None:
            session_queue.put(json.dumps(work_output))
      time.sleep(2)

def spinup_server(manager_config):
   reg_queue          = multiprocessing.SimpleQueue()
   worker_msg_queue   = multiprocessing.SimpleQueue()
   trainer_queue      = multiprocessing.SimpleQueue()
   session_queue      = multiprocessing.SimpleQueue()

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
         manager_client, worker_msg_queue, reg_queue, trainer_queue, session_queue
      )
   )

   p3 = multiprocessing.Process(
      target=trainer_process,
      args=(
         # config, queue for new sessions, model, environment
         manager_config, session_queue, trainer_queue, None, None
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

   test_config = utils.to_named_thing(test_config_dict)
   spinup_server(test_config)

if __name__ == "__main__":
   main(sys.argv)
