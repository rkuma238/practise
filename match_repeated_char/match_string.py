import re
input = "hello asdddsadfas"

for match in re.finditer(r"(\S)\1{1,}",input):
  (match[0])
