import requests
import mmap

f = open('/media/jg/24aee1e5-3eae-44a2-905d-aa7923b69d48/nmt_training_output/nmt_2019-05-09-08-56-35.624988/nmt_checkpoint-170281.data-00000-of-00001', 'rb')
files = {'file': f}
r = requests.put('http://192.168.1.15:8000', files=files)
print(r.text)
f.close()