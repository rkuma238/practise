def meta_func(name, bases, attrs):
    print('meta function called with', name, bases, attrs)
    print ([attrs[key] for key in attrs])
    nattrs = {'mod' + key:attrs[key] for key in attrs}
    return type(name, bases, nattrs)
 
MyMeta = meta_func
 
class Kls(metaclass=MyMeta):
    def setd(self, data):
        self.data = data
 
    def getd(self):
        return self.data
 
k = Kls()
k.modsetd('arun')
print(k.modgetd())
print(dir(k))
