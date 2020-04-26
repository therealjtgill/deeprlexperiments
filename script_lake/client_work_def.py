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

   def do_work(dynamic_work_params):
      if self.work_stuff is None:
         output_table_name = dynamic_work_params.output_table_name
         print("work def has nothing to do, so... inserting random data in the table.")
         random_data = np.random.rand(100, 4)
         field_placeholders = ", ".join(["{}",]*random_data.shape[1])
         column_names = ", ".join(
            ["col_" + str(i) for i in range(random_data.shape[1])]
         )
         for i in range(random_data.shape[0]):
            random_stuff = random_data[i, :]
            self.cursor.execute(
               "insert into `" + output_table_name + \
               "`(" + column_names + ")" + \
               "values(" + field_placeholders + ");".format(*random_stuff)
            )
            #self.cursor.fetchall()
         # Have to commit so that insertion actually happens.
         self.db.commit()
         print("Put some random data into the table", output_table_name)
      else:
         ret_vals = self.work_stuff.do_work(dynamic_work_params)