import abc

class Abstract(metaclass =abc.ABCMeta):
    @abc.abstractmethod
    def walk(self):
       "data"
    
    @abc.abstractmethod 
    def talk(self):
       "data"



class new_class(Abstract):
    def __init__(self,num):
       self.var= num

    def walk(self):
       print(self.var)
       print("walk")

    def talk(self):
       print(self.var)
       print("talk")

    


a = new_class(10)  
a.walk()
a.talk() 


