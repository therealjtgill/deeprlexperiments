import urllib.request
import mmap

#fname = 'nmt_checkpoint-170281.data-00000-of-00001'
#fname = 'nmt_checkpoint-170281.index'
fname = 'nmt_checkpoint-170281.meta'
f = open('/media/jg/24aee1e5-3eae-44a2-905d-aa7923b69d48/nmt_training_output/nmt_2019-05-09-08-56-35.624988/' + fname, 'rb')

mmapped_file_as_string = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

# Do the request
request = urllib.request.Request("http://192.168.1.15:8000", mmapped_file_as_string)
request.add_header("Content-Type", "application/zip")
request.add_header("Content-Disposition", fname)
request.get_method = lambda: 'PUT'
response = urllib.request.urlopen(request)
print(response.info())
print(response.read())
#close everything
mmapped_file_as_string.close()
f.close()

# Now re-download the thing we just uploaded (veracity)
response = urllib.request.urlopen('http://192.168.1.15:8000/' + fname)
data = response.read()

with open(fname, 'wb') as f:
   f.write(data)
