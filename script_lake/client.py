import json
import multiprocessing
import paho.mqtt.client as mqtt
import sys
import time
import utils

class Client(object):
    def __init__(self, client_config, client_queue, debug=False):
        self.config = client_config
        self.queue = client_queue

        self.worker_uid = client_config.worker_uid

        self.client = mqtt.Client()
        self.client.on_message = self.on_message
        self.client.on_connect = self.on_connect

        self.client.connect(self.config.broker_url, self.config.broker_port)

        for topic in self.config.topics:
            self.client.subscribe(topic.name, qos=1)

        self.listen_topic = [
            e.name for e in self.config.topics if e.action == "listen"
        ][0]

        self.publish_topic = [
            e.name for e in self.config.topics if e.action == "publish"
        ][0]

    def on_connect(self, client, userdata, flags, rc):
        client.publish(
            topic=self.publish_topic,
            payload=json.dumps(client_config),
            qos=1,
            retain=False
        )

    def on_message(self, client, userdata, message):
        if str(message.topic) == str(self.listen_topic):
            decoded_message = message.payload.decode("utf-8")
            print("\nreceived message", decoded_message, message.topic)
            print(str(message.topic), self.listen_topic)
            print("object on_message", self.queue.empty(), self.queue)
            self.queue.put(decoded_message)
            self.client.publish(
                topic=self.publish_topic,
                payload="send"
            )

    def run_de_loop(self):
        self.client.loop_forever()

    def publish(self, message):
        self.client.publish(
            self.publish_topic,
            message
        )

def mqtt_process(worker_client):
    print("Started mqtt process")
    worker_client.run_de_loop()
    while True:
        time.sleep(1)

def work_process(work_queue, worker_client):
    print("Started work process")
    current_work = None
    while True:
        print(work_queue.empty(), work_queue)
        if not work_queue.empty():
            new_work_json = work_queue.get()
            print(type(new_work_json), new_work_json)
            new_work = json.loads(new_work_json, object_hook=utils.named_thing)
            print("Doing work:\n", new_work_json)
            time.sleep(2)
            response = {
                "worker_uid": str(worker_client.worker_uid),
                "random_str": str(time.time()),
                "task_uid": str(new_work.task_uid) # lul
            }
            worker_client.publish(json.dumps(response))
        time.sleep(1)
        print("looping work")

def spinup_worker(worker_config):
    work_queue = multiprocessing.SimpleQueue()
    worker_mqtt = Client(worker_config, work_queue)

    p1 = multiprocessing.Process(
        target=mqtt_process,
        args=(
            worker_mqtt,
        )
    )

    p2 = multiprocessing.Process(
        target=work_process,
        args=(
            work_queue,
            worker_mqtt
        )
    )

    jobs = [p1, p2]

    for j in jobs:
        j.start()

def main(argv):
    test_config_dict = {
        "broker_url": "192.168.1.4",
        "broker_port": 1883,
        "topics": [
            {
                "name": "manager",
                "action": "listen"
            },
            {
                "name": "worker",
                "action": "publish"
            }
        ],
        "worker_uid": 1
    }

    test_config_json = json.dumps(test_config_dict)

    test_config = json.loads(
        test_config_json,
        object_hook=utils.named_thing
    )

    # client_obj = Client(
    #     test_config,
    #     multiprocessing.SimpleQueue()
    # )

    # client_obj.run_de_loop()
    
    spinup_worker(test_config)
    print("exiting main loop")

if __name__ == "__main__":
    main(sys.argv)
