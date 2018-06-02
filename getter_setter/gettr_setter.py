class Person(object):
  def __init__(self,value):
    self._name = value

  @property
  def name(self):
    return(self._name)  

  @name.setter
  def name(self,value):
    print("I am in setter")
    self._name = value
   
  @name.deleter
  def name(self):
    self._name = None  

p = Person("ajay")
p.name = "Rakesh"
print(p.name) 


