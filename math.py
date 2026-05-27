from sympy import *

# Define variable
x = Symbol('x')

# Input function
g = input('Enter the function to be integrated: ')
f = lambdify(x, g)

# Input limits and subintervals
a = float(input('Enter lower limit value : '))
b = float(input('Enter upper limit value : '))
n = int(input('Enter number of subintervals : '))

# Step size
h = (b - a) / n

# First and last terms
I1 = f(a) + f(b)

print("\nThe Data table:\n")
print('x(i) \t\t y(i)')

print('%0.4f \t\t %0.4f' % (a, f(a)))

I2 = 0
I3 = 0

# Calculating intermediate terms
for i in range(1, n):
    k = a + i * h

    if (i % 3 == 0):
        I2 = I2 + 2 * f(k)
    else:
        I3 = I3 + 3 * f(k)

    print('%0.4f \t\t %0.4f' % (k, f(k)))

print('%0.4f \t\t %0.4f' % (b, f(b)))

# Simpson's 3/8 Rule Formula
I = (3 * h / 8) * (I1 + I2 + I3)

print("\nIntegration result by Simpson's 3/8 rule is: %0.4f" % I)