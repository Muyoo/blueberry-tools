# encoding: utf8


def factorial(number):
    factorial = 1
    for i in range(1, number + 1):
        factorial *= i

    return factorial


def Bernoulli(p, k, n):
    c = factorial(k) / factorial(n)

    return c * (p**k) * ((1-p)**(n-k))


def accumulated_Bernoulli(p, k, n):
    return sum([Bernoulli(p, i, n) for i in range(k, n+1)])
