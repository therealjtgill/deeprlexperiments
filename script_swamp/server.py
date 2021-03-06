from functools import reduce
import gym
import json
import multiprocessing
import paho.mqtt.client as mqtt
import sys
import tensorflow as tf
import time

from work_container import WorkContainer
from pendulum_networks import PendulumNetworks
from server_work_def import ServerWorkDef, SessionManager
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

def mqtt_process(manager_client):
   print("Started mqtt process") 
   manager_client.run_de_loop()

def manager_process(
   manager_client,
   worker_msg_queue,
   reg_queue,
   trainer_in_queue,
   trainer_out_queue
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
      print("\n\n\nGrabbing new workers")
      new_workers = utils.extract_json_from_queue(reg_queue)

      session_manager.add_workers(new_workers)

      if session_manager.session_active:
         print("Session is active, looking for completed work")
         completed_work = utils.extract_json_from_queue(worker_msg_queue)
         if len(completed_work) > 0:
            print("\tFound some completed work:", completed_work)
         if session_manager.attempt_end_session(completed_work):  
            print("\tSuccessfully ended the session", session_manager.current_session.session_uid)
            # If all work is completed give it to trainer for training.
            training_table_names = [c.table_name for c in completed_work]
            session_request = session_manager.session_request(training_table_names)
            print("\t\tPutting in the session request:", session_request)
            trainer_in_queue.put(str(session_request))
            #session_params = session_manager.start_session()

      print("Grabbing list of new sessions")
      new_work = utils.extract_json_from_queue(trainer_out_queue)
      print("all worker uids:", session_manager.all_worker_uids)
      if (len(new_work) == 0) \
         and (not session_manager.first_session_started) \
         and (len(session_manager.all_worker_uids) > 0
      ):
         session_request = session_manager.session_request()
         print("Putting a session request into the trainer queue:", session_request)
         trainer_in_queue.put(str(session_request))
         
      elif (len(new_work) > 0):
         print("New work is available, making new work active")
         # If new work is available for the workers, mark the work as new in
         # the session manager and publish it to the workers.
         session_manager.start_session(new_work[-1])
         manager_client.publish(str(session_manager.current_session))

      time.sleep(2)

def trainer_process(
   manager_config,
   trainer_out_queue,
   trainer_in_queue,
   model,
   environment
):
   pendulum = gym.make("Pendulum-v0")
   session = tf.Session()
   print(pendulum.observation_space.shape)
   print(pendulum.action_space)
   num_actions = len(pendulum.action_space.high)
   agent = PendulumNetworks(
      session,
      pendulum.observation_space.shape[0],
      num_actions
   )

   train_config = WorkContainer(agent, pendulum)

   print("size of action space:", train_config.get_action_size())
   current_work = ServerWorkDef(manager_config, train_config)
   work_output  = None
   while True:
      session_requests = utils.extract_json_from_queue(trainer_in_queue)
      if len(session_requests) > 0:
         print("training session?", session_requests[-1])
         if session_requests[-1].session_uid == 1:
            print("Putting together default work for workers", session_requests[-1].worker_uids)
            work_output = current_work.default_work(session_requests[-1])
            print("\tDefault work output: ", work_output)
         else:
            print("Doing work from session request:", session_requests[-1])
            work_output = current_work.do_work(session_requests[-1])

         if work_output is not None:
            trainer_out_queue.put(json.dumps(work_output))
      time.sleep(2)

def spinup_server(manager_config):
   reg_queue         = multiprocessing.SimpleQueue()
   worker_msg_queue  = multiprocessing.SimpleQueue()
   trainer_in_queue  = multiprocessing.SimpleQueue()
   trainer_out_queue = multiprocessing.SimpleQueue()

   manager_client = Server(
      manager_config,
      {
         "register": reg_queue,
         "worker": worker_msg_queue,
         "trainer": trainer_in_queue
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
         manager_client, worker_msg_queue, reg_queue, trainer_in_queue, trainer_out_queue
      )
   )

   p3 = multiprocessing.Process(
      target=trainer_process,
      args=(
         # config, queue for new sessions, model, environment
         manager_config, trainer_out_queue, trainer_in_queue, None, None
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
     "sql_dbname": "XPDB",
     "fs_hostname": "192.168.1.15",
     "fs_port": 8000
   }

   test_config = utils.to_named_thing(test_config_dict)
   spinup_server(test_config)

if __name__ == "__main__":
   main(sys.argv)
