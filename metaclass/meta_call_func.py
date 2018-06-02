class MyMeta(type):
    def __call__(clsname, *args):
        print('MyMeta called with')
        print('clsname:', clsname)
        print('args:', args)
        instance =  object.__new__(clsname)
        instance.data = args[0] 
       # instance.__init__(*args)
        return instance
 
 
class Kls(metaclass=MyMeta):
    def __init__(self, data):
        self.data = data
 
    def printd(self):
        print(self.data)
 
ik = Kls('arun')
ik.printd()
