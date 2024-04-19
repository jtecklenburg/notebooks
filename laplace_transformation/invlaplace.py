from numpy import tile, log2, zeros, exp, size
from numpy import arange, real, pi, meshgrid, array
from numpy.fft import ifft

def crump(fun, t, pmax=10000, nel=1):

    #nt = length(t)      # number of timesteps 
    nt = max(t.shape)

    # Parameter for inverse Laplace
    fak = 1.4
    T=fak*t[-1]         # Length of Fourier series

    # pmax = 10000       # Use the first pmax values for approximation

    Er=10e-8
    sg0=0.001
    sg=sg0-log2(Er)/(2*T)

    # Algorithm
    frequencies = sg + arange(1, pmax) * pi * 1j / T         # Discrete frequencies in Laplace domain

    f = zeros((nel, nt))
    f = f + 1/2 * tile(fun(sg), (1, nt))

    for p, s in zip(arange(1, pmax), frequencies): 
        f = f + real(fun(s)*exp(1j*p*pi*t/T))

    f=f*tile(exp(sg*t)/T, (nel, 1))

    return f.transpose()

def iseger(fun, t):
# Lf: anonymous function for the Laplace transform calculation
# t: column vector of times from 0 to tmax
# ft: inverse transform -> same size as t

    nt=size(t)
    dt=max(t)/(nt-1)

    # parameter settings
    N=8*nt
    a=44/N
    
    # Numerical values of lambda and beta (see Ref. [7] p. 29)
#    li= array([0, 6.28318530717958, 12.5663706962589, 
#        18.8502914166954, 25.2872172156717, 
#        34.2969716635260, 56.1725527716607, 
#        170.533131190126])

#    bi= array([1, 1.00000000000004, 1.00000015116847, 
#        1.00081841700481, 1.09580332705189,
#        2.00687652338724, 5.94277512934943,
#        54.9537264520382])

    li = array([ 0, 6.28318530717958, 12.5663706143592, 
           18.8495559215388, 25.1327412287184, 
           31.4159265359035, 37.6991118820067, 
           43.9823334683971, 50.2716029125234, 
           56.7584358919044, 64.7269529917882, 
           76.7783110023797, 96.7780294888711, 
           133.997553190014, 222.527562038705, 
           669.650134867713 ])

    bi = array([ 1, 1, 1, 1, 1, 1.00000000000895,   
         1.00000004815464, 1.00003440685547,  
         1.00420404867308, 1.09319461846681, 
         1.51528642466058, 2.4132076646714,   
         4.16688127092229, 8.3777001312961,   
         23.6054680083019, 213.824023377988 ]) 


    c = 2*1j*pi/N
    li = a+1j*li
    k = arange(0, N+1)
 

    # the following line may be replaced by a loop on n=sizeli in order
    # to avoid memory failure for huge values of nt=size(t) ~= 10^6
    [k,li] = meshgrid(k,li)
    s = (li+c*k)/dt
    ft = real(fun(s))
    ft = 4 * bi @ ft / dt
    ft[0] = 0.5*(ft[0]+ft[N])

    # discrete Fourier’s inversion
    ft=ifft(ft[0:N])
    ft=real(exp(a*arange(0, nt))*(ft[0:nt]))

    return ft



if __name__ == "__main__":

    from numpy import size
    import matplotlib.pyplot as plt

    def L(p): return 1/p*1/(1+exp(-p))

    dt = 0.01
    t = arange(0, 20+dt, dt)

    nt = size(t)

    ft1 = crump(L, t)
    ft2 = iseger(L, t)

    plt.plot(t, ft1, t, ft2)
    plt.xlabel('t')
    plt.ylabel('f(t)')
    #plt.legend('Crump', 'Den Iseger');
    plt.show()
