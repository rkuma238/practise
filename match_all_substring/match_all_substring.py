a,b=(raw_input() for i in range(2))
cnt=0
for i in range(len(a)-len(b)+1):
	if a[i:i+len(b)]==b:
		cnt+=1
print cnt
