import multiprocessing
import sys
import paho.mqtt.client as mqtt
import time

def message_handler(client, userdata, message, queue=None):
   if not message.topic == "manager":
      return
   decoded_msg = message.payload.decode()
   print("Received message: ", decoded_msg)
   if queue is not None:
      queue.put(decoded_msg)
   else:
      print("Queue is not defined, worker won't do anything")

def mosquito(name, client):
   client.loop_forever()

def worker(client, write_topic, control_q):
   while True:
      if not control_q.empty():
         print("Worker process found a new thing to do!")
         new_job = control_q.get()
         for _ in range(50000000):
            a = 1
         print("Finished the job")
         client.publish(write_topic, payload="finished")

def main(argv):
   jobs = []
   queue_of_things = multiprocessing.SimpleQueue()

   mh = lambda x, y, z: message_handler(x, y, z, queue=queue_of_things)
   client = mqtt.Client()
   client.on_message = mh
   client.connect(argv[1], 1883)
   client.subscribe("worker", qos=1)
   client.subscribe("manager", qos=1)

   for i in range(1):
      p = multiprocessing.Process(
         target=mosquito,
         args=(
            str(i),
            client
         )
      )
      jobs.append(p)

   p = multiprocessing.Process(
      target=worker,
      args=(
         client, "worker", queue_of_things
      )
   )
   jobs.append(p)

   for j in jobs:
      j.start()

if __name__ == "__main__":
   main(sys.argv)