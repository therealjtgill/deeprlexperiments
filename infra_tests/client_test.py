import json
import paho.mqtt.client as mqtt
import sys

def message_handler(client, userdata, message):
    if message.topic is not "manager":
        return
    print("Received message: ", message.payload.decode())
    sample_dict = {
        "key1": "val1",
        "key2": "val2",
        "key3": ["l1", "l2", "l3"]
    }
    #client.publish(topic="worker", payload="new_task", qos=0, retain=False)
    client.publish(topic="worker", payload=json.dumps(sample_dict), qos=0, retain=False)

def main(argv):
    broker_url = argv[1]
    broker_port = 1883
    client = mqtt.Client()
    client.on_message = message_handler
    client.connect(broker_url, broker_port)
    topic_name = "worker"
    client.subscribe(topic_name, qos=1)
    client.subscribe("manager", qos=1)
    client.publish(topic=topic_name, payload="fuckshitpiss", qos=0, retain=False)

    client.loop_forever()

if __name__ == "__main__":
    main(sys.argv)
