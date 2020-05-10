# Straight from readthedocs
import os

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

def main():
   authorizer = DummyAuthorizer()

   authorizer.add_user('users', '12345', '.', perm='elradfmwMT')
   authorizer.add_anonymous(os.getcwd())

   handler = FTPHandler
   handler.authorizer = authorizer

   handler.banner = "pyftpdlib based ftpd ready"

   address = ('', 2121)
   server = FTPServer(address, handler)

   server.max_cons = 256
   server.max_cons_per_ip = 5

   server.serve_forever()

if __name__ == "__main__":
   main()