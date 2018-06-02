from netaddr import IPNetwork
import subprocess
import threading
import os
class ping_ip(threading.Thread):
      def __init__(self,ip):
          self.ip = ip
          self.stdout = None
          self.stderr = None
          threading.Thread.__init__(self)

      def run(self):
           self.ip = str(self.ip)
           toping = Popen(['ping','-c','3',self.ip],stdout=PIPE)
           output = toping.communicate()[0]
           hostlive = toping.returncode
           if hostlive == 0:
              print(self.ip,"is alive")
           else:
              print(self.ip,"is not alive") 
 
input = input("Enter the IP addresss: ")
for ip in IPNetwork(input):
    print(ip)
    ping_test = ping_ip(ip)
    ping_test.start() 
