def smart_divide(func):
   def inner():
       print("I am in decorator")
       func()  
   return inner

@smart_divide
def divide():
    print("I am in actual_function")


divide()
