import paho.mqtt.client as mqtt
import sys

def message_handler(client, userdata, message):
    print("Received message: ", message.payload.decode())
    return

def main(argv):
    broker_url = argv[1]
    broker_port = 1883
    client = mqtt.Client()
    client.on_message = message_handler
    client.connect(broker_url, broker_port)
    topic_name = "thisismytopic"
    client.subscribe(topic_name, qos=1)
    client.publish(topic=topic_name, payload="fuckshitpiss", qos=0, retain=False)

    message_counter = 0
    while(True):
        for i in range(5000000):
            a = 1
        client.publish(topic_name, payload="trollolol" + str(message_counter), qos=0, retain=False)
        if (message_counter % 10) == 0:
            client.publish(topic_name, payload="send", qos=0, retain=False)
        message_counter += 1

    #client.loop_forever()

if __name__ == "__main__":
    main(sys.argv)
