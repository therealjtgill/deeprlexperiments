import json

class named_thing(object):
   def __init__(self, args):
      self.__dict__.update(args)

   def __str__(self):
      return self.__repr__()

   def __repr__(self):
      return "\n".join(str(k) + ": " + str(v) for k, v in self.__dict__.items())

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