import copy
import glob
import numpy as np
import pandas as pd
import pymysql
import sys
import time

#from network import WorkContainer
from work_container import WorkContainer
import utils

class ServerWorkDef(object):
   def __init__(self, static_work_params, work_stuff=None):
      self.config = static_work_params
      self.num_train_loops = 5
      self.work_stuff = work_stuff
      self.column_names = ["time", "state", "action", "reward"]
      if self.work_stuff is not None:
         state_size  = self.work_stuff.get_state_size()
         action_size = self.work_stuff.get_action_size()
         self.action_names = ["action_" + str(i) for i in range(action_size)]
         self.state_names = ["state_" + str(i) for i in range(state_size)]
         self.next_state_names = ["next_state_" + str(i) for i in range(state_size)]
         self.column_names = [
            "time",
            "reward",
            "discounted_reward",
            *self.state_names,
            *self.action_names,
            *self.next_state_names
         ]
         self.query_column_names = [c for c in self.column_names if "time" not in c]

      sql_pass = utils.decrypt_ciphertext(self.config.sql_key_loc)

      self.db = None
      self.cursor = None
      try:
         self.db = pymysql.connect(
            self.config.sql_hostname,
            self.config.sql_username,
            sql_pass,
            self.config.sql_dbname
         )
         sql_pass = None
         del sql_pass
         self.cursor = self.db.cursor()

      except Exception as e:
         print("Couldn't connect to remote SQL database.", str(e))
         sys.exit(-1)

      self.http_handler = utils.SimpleHttpStorage(
         static_work_params.fs_hostname,
         static_work_params.fs_port
      )

   def __make_new_tables(self, table_name_base, worker_uids):
      new_table_names = []
      for w_uid in worker_uids:
         new_table_name = table_name_base + "_" + str(w_uid)
         # This needs to be changed to match the schema of the environment.
         try:
            # self.cursor.execute(
            #    "create table `" + new_table_name + "`" + \
            #    "(time float, state float, action float, reward float)"
            # )
            column_schema = [
               c + " float" for c in self.column_names
            ]
            self.cursor.execute(
               "create table `" + new_table_name + "`" + \
               "(" + ", ".join(column_schema) + ")"
            )
            self.cursor.fetchall()
            new_table_names.append(
               {
                  "table_name": new_table_name,
                  "worker_uid": w_uid
               }
            )
         except Exception as e:
            print("Error occurred trying to make a new table for the workers.")
            print(str(e))
      return new_table_names

   def default_work(self, dynamic_work_params):
      output_params = None
      new_table_name_base = utils.today_string()
      print(
         "work def is undefined, making default new tables with base name",
         new_table_name_base
      )
      new_table_names = self.__make_new_tables(
         new_table_name_base, dynamic_work_params.worker_uids
      )

      if len(new_table_names) > 0:
         output_params = {
            "session_uid": dynamic_work_params.session_uid,
            "worker_uids": dynamic_work_params.worker_uids,
            "work_params": {
               "new_table_names": new_table_names,
               "num_rollouts": 50,
               "checkpoint_name": str(np.random.randint(0, 1000)),
               "checkpoint_filenames": []
            }
         }
      return output_params

   def do_work(self, dynamic_work_params):
      output_params = None
      if self.work_stuff is None:
         output_params = self.default_work(dynamic_work_params)
      else:
         new_table_name_base = utils.today_string()
         new_table_names = self.__make_new_tables(
            new_table_name_base, dynamic_work_params.worker_uids
         )

         action_rollouts = []
         state_rollouts = []
         discounted_reward_rollouts = []
         reward_rollouts = []
         next_state_rollouts = []
         for table_name in dynamic_work_params.table_names:
            df = pd.read_sql(
               "select " + ", ".join(self.query_column_names) + " from " +
               "`" + table_name + "`", 
               self.db
            )
            action_rollouts.append(df[self.action_names])
            state_rollouts.append(df[self.state_names])
            next_state_rollouts.append(df[self.next_state_names])
            discounted_reward_rollouts.append(df["discounted_reward"])
            reward_rollouts.append(df["reward"])

         for i in range(self.num_train_loops):
            train_index = np.random.choice(len(action_rollouts))
            self.work_stuff.train_batch(
               state_rollouts[train_index],
               action_rollouts[train_index],
               discounted_reward_rollouts[train_index],
               reward_rollouts[train_index],
               next_state_rollouts[train_index]
            )

         checkpoint_name = utils.today_string()
         self.work_stuff.save_params(checkpoint_name)
         checkpoint_filenames = glob.glob(checkpoint_name + "*")

         output_params = {
            "session_uid": dynamic_work_params.session_uid,
            "worker_uids": dynamic_work_params.worker_uids,
            "work_params": {
               "new_table_names": new_table_names,
               "num_rollouts": 50,
               "checkpoint_name": checkpoint_name,
               "checkpoint_filenames": checkpoint_filenames
            }
         }

      print("server work def returning these output params:", output_params)
      return output_params

class SessionManager(object):
   def __init__(
      self,
      session_timeout_s=20,
      default_worker_uids=[],
      default_session_uid=0
   ):
      self.all_worker_uids = default_worker_uids
      self.session_timeout = session_timeout_s
      self.available_worker_uids = self.all_worker_uids

      self.completed_session = utils.to_named_thing(
         {
            "session_uid": 0,
            "worker_uids": [],
            "start_time": 0.0,
            "end_time": 0.0,
            "completed_worker_uids": [],
            "work_params": {}
         }
      )

      self.current_session = utils.to_named_thing(
         {
            "session_uid": default_session_uid,
            "worker_uids": default_worker_uids,
            "start_time": 0.0,
            "end_time": 0.0,
            "completed_worker_uids": [],
            "work_params": {}
         }
      )

      self.first_session_started = False
      # Rollout session for workers is initially inactive
      self.session_active = False

   def add_workers(self, new_workers):
      if len(new_workers) == 0:
         return
      print("Adding workers", new_workers)
      self.all_worker_uids += [w.worker_uid for w in new_workers]
      self.all_worker_uids = list(set(self.all_worker_uids))

      self.available_worker_uids += [w.worker_uid for w in new_workers]
      self.available_worker_uids = list(set(self.available_worker_uids))
      print("Current available workers:", self.available_worker_uids)

   def session_request(self):
      session_request = utils.to_named_thing(
         {
            "session_uid": self.current_session.session_uid + 1,
            "worker_uids": self.available_worker_uids,
            #"table_names": self.current_session.work_params.new_table_names
         }
      )
      return session_request

   def start_session(self, new_work):
      self.current_session.session_uid = new_work.session_uid
      self.current_session.worker_uids = new_work.worker_uids
      self.current_session.start_time = time.time()
      self.current_session.end_time = 0.0
      self.current_session.completed_worker_uids = []
      self.current_session.work_params = new_work.work_params

      if not self.first_session_started:
         print("\tMarking the first session as started.")
         self.first_session_started = True

      self.session_active = True
      return self.current_session

   def attempt_end_session(self, completed_work):

      print("\tCompleted work being used to attempt session end:", completed_work)
      print("\tcurrent session worker uids:", self.current_session.worker_uids, [type(c) for c in self.current_session.worker_uids])
      print("\tcurrent session uid:", self.current_session.session_uid, type(self.current_session.session_uid))
      print("\tworkers that have already completed this task:", self.current_session.completed_worker_uids)
      
      for c in completed_work:
         print("\tinstance of completed work:", c)
         print("\tcompleted worker uid:", c.worker_uid, type(c.worker_uid))
         print("\tcompleted session uid:", c.session_uid, type(c.session_uid))
         worker_uid = int(c.worker_uid)
         session_uid = int(c.session_uid)
         if (worker_uid not in self.current_session.completed_worker_uids) \
            and (worker_uid in self.current_session.worker_uids) \
            and (session_uid == self.current_session.session_uid):
            print("\tFound some work that matches")
            if len(self.current_session.completed_worker_uids) == 0:
               self.current_session.end_time = time.time() + self.session_timeout

            self.current_session.completed_worker_uids.append(worker_uid)

      completed_uids = self.current_session.completed_worker_uids
      worker_uids = self.current_session.worker_uids

      if set(completed_uids) == set(worker_uids):
         self.session_active = False
         self.completed_session = self.current_session
         return True

      if (self.current_session.end_time > 0.0) and \
         (time.time() >= self.current_session.end_time):
         # Any workers that haven't replied are removed from the list of 
         # available workers. They can re-request to be added once the new
         # work is passed out.
         self.all_worker_uids = self.current_session.completed_worker_uids
         
         self.session_active = False
         self.completed_session = self.current_session
         return True
      return False
