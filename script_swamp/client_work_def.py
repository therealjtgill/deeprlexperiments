import mmap
import numpy as np
import pymysql
import sys
import time
import urllib.request

#from network.work_container import WorkContainer
#from script_swamp import utils

from work_container import WorkContainer
import utils

class ClientWorkDef(object):
   def __init__(self, static_work_params, work_stuff=None):
      self.config = static_work_params
      self.work_stuff = work_stuff
      self.column_names = ["time", "state", "action", "reward"]
      if self.work_stuff is not None:
         state_size  = self.work_stuff.get_state_size()
         action_size = self.work_stuff.get_action_size()
         self.column_names = [
            "time",
            "reward",
            "discounted_reward",
            *["state_" + str(i) for i in range(state_size)],
            *["action_" + str(i) for i in range(action_size)],
            *["next_state_" + str(i) for i in range(state_size)],
         ]

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

   def do_work(self, dynamic_work_params):
      response = None
      # This should technically be mapped to the worker UID, but for now
      # it's just a list of table names.
      output_table_name = [
         p.table_name for p in dynamic_work_params.work_params.new_table_names
         if p.worker_uid == self.config.worker_uid
      ][0]

      if self.work_stuff is None:
         print("work def undefined, inserting random data in the table.")
         random_data = np.random.rand(100, len(self.column_names))
         
         for i in range(random_data.shape[0]):
            random_stuff = random_data[i, :]
            field_data = ", ".join(
               ["{}",]*random_data.shape[1]
            ).format(*random_stuff)
            self.cursor.execute(
               "insert into `" + output_table_name + \
               "`(" + ", ".join(self.column_names) + ")" + \
               "values(" + field_data + ");"
            )
            self.cursor.fetchall()
         # Have to commit so that insertion actually happens.
         self.db.commit()
         print("Put some random data into the table", output_table_name)
         response = {
            "worker_uid": str(self.config.worker_uid),
            "random_str": str(time.time()),
            "session_uid": str(dynamic_work_params.session_uid),
            "table_name": output_table_name # Probably not necessary
         }
      else:
         # Copy checkpoint files from file server to local disk.
         work_filenames = dynamic_work_params.work_params.checkpoint_filenames
         checkpoint_name = dynamic_work_params.work_params.checkpoint_name
         print("Downloading checkpoint files named:", work_filenames)
         for filename in work_filenames:
            self.http_handler.download_file(filename)

         # Load params from the last updated checkpoint and perform the policy
         # rollout against the checkpoint.
         self.work_stuff.load_params(checkpoint_name)
         ret_dict = self.work_stuff.perform_rollout(
            dynamic_work_params.work_params.num_rollouts
         )

         # Save output from rollout to the SQL database, order of fields has
         # to match column name order.
         for i in range(len(ret_dict["states"])):
            field_list = [
               i, # Just let this happen; time field is a counter :'(
               *ret_dict["rewards"][i],
               *ret_dict["discounted_rewards"][i],
               *ret_dict["states"][i],
               *ret_dict["actions"][i],
               *ret_dict["next_states"][i]
            ]
            print("Field list I\'m trying to write:", field_list)
            field_list = [str(f) for f in field_list]
            field_data = ", ".join(field_list)
            self.cursor.execute(
               "insert into `" + output_table_name + \
               "`(" + ", ".join(self.column_names) + ")" + \
               "values(" + field_data + ");"
            )
            self.cursor.fetchall()
         # Have to commit so that insertion actually happens.
         self.db.commit()

         # Delete the network checkpoints after they've been loaded and rolled out.
         for filename in work_filenames:
            os.remove(filename)

         response = {
            "worker_uid": str(self.config.worker_uid),
            "random_str": str(time.time()),
            "session_uid": str(dynamic_work_params.session_uid),
            "table_name": output_table_name
         }
      return response