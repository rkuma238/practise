
"""There is a python module dedicated to permutations and combinations called itertools."""


import itertools
"""The permutation function allows you to get permutation of N values within a list, where order matters. For instance, selecting N=2 values with [1,2,3] is done as follows"""


list(itertools.permutations([1,2,3], 2))
"""[(1, 2), (1, 3), (2, 1), (2, 3), (3, 1), (3, 2)]
1
2"""

print(list(itertools.permutations([1,2,3], 2)))

"""[(1, 2), (1, 3), (2, 1), (2, 3), (3, 1), (3, 2)]
If order is not important, you can use combinations:"""

print(list(itertools.combinations([1,2,3], 2)))
"""[(1, 2), (1, 3), (2, 3)]
1
2"""


print (list(itertools.combinations([1,2,3], 2)))
"""[(1, 2), (1, 3), (2, 3)]"""

"""Then, you may want to build all possible arrays of N values taken from a list of possible values. For instance, you may want to build a vector of length N=3 made of 0 and 1. This can be done with the cartesian product function:"""

print (list(itertools.product([0,1], repeat=3)))

"""[(0, 0, 0), (0, 0, 1), (0, 1, 0), (0, 1, 1), (1, 0, 0), 
(1, 0, 1), (1, 1, 0), (1, 1, 1)]
1
2
3"""




print (list(itertools.product([0,1], repeat=3)))
"""[(0, 0, 0), (0, 0, 1), (0, 1, 0), (0, 1, 1), (1, 0, 0), 
(1, 0, 1), (1, 1, 0), (1, 1, 1)]"""

