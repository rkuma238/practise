import re
import os
path = "/Users/rakesh/Downloads/python_practise"

i = os.listdir(path)
File = []
Directory = []
Dir = []
Directory.append(path)
while(Directory):
   i = os.listdir(Directory[0])
   
   for j in i:
    if os.path.isdir(os.path.join(Directory[0],j)):
       Dir.append(j)
       Directory.append(Directory[0] + '/' + j)  
    else:
      File.append(j)
   del Directory[0]

print("File: %s"%File)
print("Directory: %s"%Dir)
