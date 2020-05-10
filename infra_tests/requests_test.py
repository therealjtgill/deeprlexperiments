import urllib2
import mmap

f = open('/media/jg/24aee1e5-3eae-44a2-905d-aa7923b69d48/nmt_training_output/nmt_2019-05-09-08-56-35.624988/nmt_checkpoint-208121.data-00000-of-00001', 'rb')

mmapped_file_as_string = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

# Do the request
request = urllib2.Request(url, mmapped_file_as_string)
request.add_header("Content-Type", "application/zip")
response = urllib2.urlopen(request)

#close everything
mmapped_file_as_string.close()
f.close()