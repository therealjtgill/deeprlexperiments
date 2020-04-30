import numpy as np
import pymysql
import sys
import time
import utils

class ClientWorkDef(object):
   def __init__(self, static_work_params, work_stuff=None):
      self.config = static_work_params
      self.work_stuff = work_stuff

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

   def do_work(self, dynamic_work_params):
      response = None
      if self.work_stuff is None:
         # This should technically be mapped to the worker UID, but for now
         # it's just a list of table names.
         #output_table_name = dynamic_work_params.new_table_names[0]
         output_table_name = [
            p.table_name for p in dynamic_work_params.new_table_names 
            if p.worker_uid == self.config.worker_uid
         ][0]
         print("work def has nothing to do, so... inserting random data in the table.")
         random_data = np.random.rand(100, 4)
         
         #column_names = ", ".join(
         #   ["col_" + str(i) for i in range(random_data.shape[1])]
         #)
         column_names = ["time", "state", "action", "reward"]
         for i in range(random_data.shape[0]):
            random_stuff = random_data[i, :]
            field_data = ", ".join(["{}",]*random_data.shape[1]).format(*random_stuff)
            self.cursor.execute(
               "insert into `" + output_table_name + \
               "`(" + ", ".join(column_names) + ")" + \
               "values(" + field_data + ");"
            )
            self.cursor.fetchall()
         # Have to commit so that insertion actually happens.
         self.db.commit()
         print("Put some random data into the table", output_table_name)
         response = {
            "worker_uid": str(self.config.worker_uid),
            "random_str": str(time.time()),
            "session_uid": str(dynamic_work_params.session_uid)
         }
      else:
         ret_vals = self.work_stuff.do_work(dynamic_work_params)
      return response