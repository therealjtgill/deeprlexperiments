import multiprocessing
import sys
import paho.mqtt.client as mqtt
import time

def message_handler(client, userdata, message, queue=None):
   decoded_msg = message.payload.decode()
   print("Received message: ", decoded_msg)
   if queue is not None:
      queue.put(decoded_msg)

def mosquito(name, client, control_q):
   client.loop_forever()

def worker(client, control_q):
   while True:
      if not control_q.empty():
         print("Worker process found a new thing to do!")
         new_job = q.get()
         for _ in range(50000):
            a = 1
         print("Finished the job")

def main(argv):
   jobs = []
   queue_of_things = multiprocessing.SimpleQueue()

   client = mqtt.Client()
   client.on_message = message_handler
   client.connect(argv[1], 1883)
   client.subscribe("worker", qos=1)
   client.subscribe("manager", qos=1)

   for i in range(1):
      p = multiprocessing.Process(
         target=mosquito,
         args=(
            str(i),
            client,
            queue_of_things
         )
      )
      jobs.append(p)
      p.start()

   p = multiprocessing.Process(
      target=worker,
      args=(
         client, queue_of_things
      )
   )

if __name__ == "__main__":
   main(sys.argv)