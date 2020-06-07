import datetime
import json
import mmap
import os
import urllib.request

class RemoteFileStorage(object):
   def __init__(self, **kwargs):
      self.__dict__.update(kwargs)

   def upload_file(self, filename):
      raise ValueError(
         self.__class__,
         "upload_file() requires implementation by a derived class."
      )

   def download_file(self, filename, destination=None):
      raise ValueError(
         self.__class__,
         "download_file() requires implementation by a derived class."
      )

class SimpleHttpStorage(RemoteFileStorage):
   def __init__(self, hostname, port, download_dir="."):
      self.hostname = hostname
      self.port = int(port)
      self.host_url = "http://" + str(self.hostname) + ":" + str(self.port)
      self.download_dir = download_dir

   def upload_file(self, filename):
      if not os.path.exists(filename):
         print("File", filename, " does not exist, exiting.")
         return False
      
      try:
         upload_file = open(filename, 'rb')
         mmapped_file_as_string = mmap.mmap(
            upload_file.fileno(),
            0,
            access=mmap.ACCESS_READ
         )
         request = urllib.request.Request(self.host_url, mmapped_file_as_string)
         request.add_header("Content-Type", "application/zip")
         filename_sans_path = filename.split(os.sep)[-1]
         request.add_header("Content-Disposition", filename_sans_path)
         request.get_method = lambda: 'PUT'
         response = urllib.request.urlopen(request)

         mmapped_file_as_string.close()
         upload_file.close()
         return True
      except Exception as e:
         print("Encountered exception trying to upload file:", str(e))
         return False

   def download_file(self, filename, destination=None):
      try:
         response = urllib.request.urlopen(self.host_url + "/" + filename)
         data = response.read()

         if destination is None:
            destination = self.download_dir

         full_filename = os.path.join(destination, filename)
         with open(full_filename) as outfile:
            outfile.write(data)
         return True, full_filename
      except Exception as e:
         print("Encountered exception while downloading file", filename, "to", destination)
         print(str(e))
         return False, ""

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