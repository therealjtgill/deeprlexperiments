import argparse
import datetime
import numpy as np
import pymysql
import sys

def main(argv):
   parser = argparse.ArgumentParser(
      description="Test connection to remote mysql db"
   )

   parser.add_argument("-u", "--username",
      help     = "Username for connection to remote DB.",
      required = True
   )
   parser.add_argument("-p", "--password",
      help     = "User password",
      required = True
   )
   parser.add_argument("--hostname",
      help     = "Hostname or IP address of remote host.",
      required = True
   )
   parser.add_argument("--dbname",
      help     = "Name of the DB that will be connected to.",
      required = True
   )

   args = parser.parse_args()

   db = None
   try:
      db = pymysql.connect(
         args.hostname,
         args.username,
         args.password,
         args.dbname
      )
   except Exception as e:
      print("Couldn't connect to remote SQL database.", str(e))
      sys.exit(-1)

   # Cursor is like the command-line cursor for mysql, pass commands as strings
   cursor = db.cursor()

   new_table_name = str(datetime.datetime.today()).replace(":", "-").replace(" ", "-")

   # Assumes that single states and actions can be taken in this fake environment
   cursor.execute("create table `" + new_table_name + "`(time float, state float, action float, reward float)")
   cursor.fetchall()

   for i in range(100):
      random_stuff = np.random.rand(4)
      cursor.execute(
         "insert into `" + new_table_name + "`(time, state, action, reward)" + \
         "values({}, {}, {}, {});".format(*random_stuff)
      )
      cursor.fetchall()
   # Have to commit so that insertion actually happens.
   db.commit()

if __name__ == "__main__":
   main(sys.argv)
