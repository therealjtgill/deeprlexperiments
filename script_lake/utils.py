import datetime
import json

def to_named_thing(input_data):
   input_data_str = json.dumps(input_data)
   output_data = json.loads(
      input_data_str,
      object_hook=named_thing,
      parse_int=int,
      parse_float=float
   )
   return output_data

def extract_json_from_queue(queue):
   extracted_items = []
   while not queue.empty():
      try:
         queue_data_str = queue.get()
         queue_data = json.loads(
            queue_data_str,
            object_hook=named_thing,
            parse_int=int,
            parse_float=float
         )
         extracted_items.append(
            queue_data
         )
      except Exception as e:
         print("Couldn't decode string from the queue, might not be JSON.")
         print(queue_data_str)
         print("Error:", str(e))
   return extracted_items

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
   print("test config json:", test_config_json)
   test_config_object = json.loads(test_config_json, object_hook=named_thing)

   test_config_str = str(test_config_object)
   print("Type of json-ified str:", type(json.loads(test_config_str)))
   print("str equals json?:", test_config_str == test_config_json)
   print("test config str:", test_config_str)
   print("first chars:", test_config_str[0], test_config_json[0])

   print(
      test_config_object.broker_url,
      test_config_object.topics
   )