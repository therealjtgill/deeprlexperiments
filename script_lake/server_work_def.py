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
         try:
            self.cursor.execute(
               "create table `" + new_table_name + "`" + \
               "(time float, state float, action float, reward float)"
            )
            self.cursor.fetchall()
            new_table_names.append(new_table_name)
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
               "session_uid": "%010d" % self.session_uid
            }
            self.session_uid += 1
      else:
         ret_vals = self.work_stuff.do_work(dynamic_work_params)
         output_params = {
         }

      self.current_session = utils.to_named_thing(output_params)
      return output_params