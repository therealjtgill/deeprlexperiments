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
      output_params = None
      if self.work_stuff is None:
         new_table_name_base = utils.today_string()
         new_table_names = []
         print("work def has nothing to do, so... making a new tables with base name", utils.today_string())
         for w_uid in dynamic_work_params.worker_uids:
            new_table_name = new_table_name + "_" + str(w_uid)
            cursor.execute(
               "create table `" + new_table_name + "`" + \
               "(time float, state float, action float, reward float)"
            )
            cursor.fetchall()
            new_table_names.append(new_table_name)
         output_params = {
            "new_table_names": new_table_names,
         }
      else:
         ret_vals = self.work_stuff.do_work(dynamic_work_params)