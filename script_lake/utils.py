import datetime
import json

class named_thing(object):
   def __init__(self, args):
      self.__dict__.update(args)

   def __str__(self):
      return self.__repr__()

   def __repr__(self):
      # This makes the class perfectly parsable by the JSON package.
      return str(self.__dict__).replace("\'", "\"")

class logger(object):
   def __init__(self, my_name, out_filename=None, parent=None):
      self.my_name = None
      self.printer = None
      self.out_file = None
      if parent is not None:
         self.my_name = parent.my_name + "." + my_name
         self.printer = parent.printer
      else:
         self.my_name = my_name
         if out_filename is not None:
            try:
               self.out_file = open(out_filename, "r")
            except Exception as e:
               print("\nCould not open file named:", out_filename)
               print("Writing to stdout instead.", str(e))
               self.out_file = None
            if self.out_filename is not None:
               self.printer = self.write_to_file
            else:
               self.printer = lambda args: print(self.my_name, *args)

   def write_to_file(self, args):
      self.out_file.write(my_name + ": " + " ".join([str(a) for a in args] + "\n"))

   def __call__(self, args):
      self.printer(args)

def today_string():
   return str(datetime.datetime.today()).replace(":", "-").replace(" ", "-")

def decrypt_ciphertext(filename):
   from cryptography.fernet import Fernet
   lines = []

   try:
      with open(filename, "r") as f:
         lines = f.readlines()
   except Exception as e:
      print("Could not open file", filename, "for unciphering.")
      return "filenotfound"

   key_line = [l for l in lines if "key" in l][0]
   key = str.encode(key_line.split("key ")[-1])

   cipher_line = [l for l in lines if "cipher" in l][0]
   cipher = str.encode(cipher_line.split("cipher ")[-1])

   cipher_suite = Fernet(key)
   unciphered_text = (cipher_suite.decrypt(cipher))
   return unciphered_text

if __name__ == "__main__":
   test_config_dict = {
      "broker_url": "192.168.1.4",
      "broker_port": 1883,
      "topics": [
         {
            "name": "worker",
            "action": "listen"
         },
         {
            "name": "manager",
            "action": "publish"
         }
      ]
   }

   test_config_json = json.dumps(test_config_dict)

   test_config_object = json.loads(test_config_json, object_hook=named_thing)

   print(
      test_config_object.broker_url,
      test_config_object.topics
   )