dict = {}
input = "hello"
for i in range(len(input)):
      if input[i] in dict.keys():
       dict[input[i]]['occurances'] += dict[input[i]]['occurances']
       dict[input[i]]['postion'].append(i)     
      else:
       dict[input[i]] = {'occurances':1 , 'postion':[i]}

print(dict)
