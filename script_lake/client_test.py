import utils
import json
import multiprocessing
import paho.mqtt.client as mqtt
import sys

class ClientCallbacks(object):
    def __init__(self, client_config, client_queue):
        self.config = client_config
        self.queue = client_queue

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
        print("listen topic:", self.listen_topic)
        print("publish topic:", self.publish_topic)

    def on_connect(self, client, userdata, flags, rc):
        print("connected")
        client.publish(
            topic=self.publish_topic,
            payload=json.dumps(client_config),
            qos=1,
            retain=False
        )

    def on_message(self, client, userdata, message):
        print("received message", message.payload, message.topic)
        print(self.listen_topic)
        print(len(message.topic), len(self.listen_topic))
        if str(message.topic) == str(self.listen_topic):
            #self.queue.put(message)
            self.client.publish(
                topic=self.publish_topic,
                payload="send"
            )

    def run_de_loop(self):
        self.client.loop_forever()

# def message_handler(client, userdata, message):
#     if message.topic is not "worker":
#         return
#     print("Received message: ", message.payload.decode())
#     client.publish(topic="manager", payload="new_task", qos=0, retain=False)

# def main(argv):
#     broker_url = argv[1]
#     broker_port = 1883
#     client = mqtt.Client()
#     client.on_message = message_handler
#     client.connect(broker_url, broker_port)
#     topic_name = "worker"
#     client.subscribe(topic_name, qos=1)
#     client.subscribe("manager", qos=1)
#     client.publish(topic="manager", payload="fuckshitpiss", qos=0, retain=False)

#     client.loop_forever()

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
        ]
    }

    test_config_json = json.dumps(test_config_dict)

    test_config = json.loads(
        test_config_json,
        object_hook=utils.named_thing
    )

    client_obj = ClientCallbacks(
        test_config,
        multiprocessing.SimpleQueue
    )

    client_obj.run_de_loop()
if __name__ == "__main__":
    main(sys.argv)
