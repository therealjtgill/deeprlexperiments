#import copy
import numpy as np
import pymysql
import sys
import time
import utils

class ServerWorkDef(object):
   def __init__(self, static_work_params, work_stuff=None):
      self.config = static_work_params
      self.work_stuff = work_stuff

      sql_pass = utils.decrypt_ciphertext(self.config.sql_key_loc)

      self.db = None
      self.cursor = None
      self.session_uid = 1
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

   def __make_new_tables(self, table_name_base, worker_uids):
      new_table_names = []
      for w_uid in worker_uids:
         new_table_name = table_name_base + "_" + str(w_uid)
         # This needs to be changed to match the schema of the environment.
         try:
            self.cursor.execute(
               "create table `" + new_table_name + "`" + \
               "(time float, state float, action float, reward float)"
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

   def do_work(self, dynamic_work_params):
      output_params = None
      if self.work_stuff is None:
         new_table_name_base = utils.today_string()
         print("work def has nothing to do, so... making a new tables with base name", new_table_name_base)
         new_table_names = self.__make_new_tables(
            new_table_name_base, dynamic_work_params.worker_uids
         )

         if len(new_table_names) > 0:
            output_params = {
               "new_table_names": new_table_names,
               "session_uid": "%010d" % self.session_uid,
               "worker_uids": dynamic_work_params.worker_uids
            }
            self.session_uid += 1
      else:
         ret_vals = self.work_stuff.do_work(dynamic_work_params)
         output_params = {
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

      self.current_session = utils.to_named_thing(
         {
            "session_uid": default_session_uid,
            "worker_uids": default_worker_uids,
            "start_time": 0.0,
            "end_time": 0.0,
            "completed_worker_uids": []
         }
      )

   def add_workers(self, new_worker_uids):
      self.all_worker_uids += new_worker_uids
      self.all_worker_uids = list(set(self.worker_uids))

   def start_session(self, worker_params):
      self.current_session.session_uid = worker_params.session_uid
      self.current_session.worker_uids = self.available_worker_uids
      self.current_session.start_time = time.time()
      self.current_session.end_time = 0.0
      self.current_session.completed_worker_uids = []

   def attempt_end_session(self, completed_work):
      for c in completed_work:
         if c.worker_uid not in self.current_session.completed_worker_uids \
            and c.worker_uid in self.current_session.worker_uids \
            and c.session_uid == self.current_session-session_uid:

            if len(self.current_session.completed_worker_uids) == 0:
               self.current_session.end_time = time.time() + self.session_timeout

            self.current_session.completed_worker_uids.append(c.worker_uid)

      completed_uids = self.current_session.completed_worker_uids
      worker_uids = self.current_session.worker_uids
      if set(completed_uids) == set(worker_uids) \
         or (
            self.current_session.end_time > 0.0 and \
            time.time() >= self.current_session.end_time
         ):
         return True
      return False
