from subprocess import Popen,PIPE
import threading
from netaddr  import IPNetwork

def ping_fun(ip):
  ip = str(ip)
  toping = Popen(['ping','-c','3',ip],stdout=PIPE)
  output = toping.communicate()[0]
  hostlive = toping.returncode
  if hostlive == 0:
     print(ip,"is alive")
  else:
     print(ip,"is not alive")


input = input("Enter the IP addresss: ")
for ip in IPNetwork(input):
    ping_test = threading.Thread(target=ping_fun, args=(ip,))
    ping_test.start()




 
