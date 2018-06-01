import re
input = "hello asdddsadfas"
a = []
for match in re.finditer(r"(\S)\1{1,}",input):
   tuple =(match[0][0],len(match[0]))
   a.append (tuple)
print(a)

""" re.findall can not be used """
 
