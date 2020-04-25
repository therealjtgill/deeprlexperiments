import utils
import json
import multiprocessing
import paho.mqtt.client as mqtt
import sys

class ClientCallbacks(object):
    def __init__(self, client_config, client_queue, debug=False):
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

    def on_connect(self, client, userdata, flags, rc):
        client.publish(
            topic=self.publish_topic,
            payload=json.dumps(client_config),
            qos=1,
            retain=False
        )

    def on_message(self, client, userdata, message):
        if str(message.topic) == str(self.listen_topic):
            self.queue.put(message)
            self.client.publish(
                topic=self.publish_topic,
                payload="send"
            )

    def run_de_loop(self):
        self.client.loop_forever()

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
        multiprocessing.SimpleQueue()
    )

    client_obj.run_de_loop()
if __name__ == "__main__":
    main(sys.argv)
