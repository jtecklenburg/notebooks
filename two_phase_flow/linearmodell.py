from numpy import linspace

def fractionalflow(Sw = linspace(0, 1, 100), muw = 0.00041017, mun = 6.3636e-05):

    # definition of fractional flow function
    def fw(Sw):
        krn = 1 - Sw # relative permeability function for nonwetting phase
        krw = Sw # relative permeability function for wetting phase

        lambdaw = krw/muw
        lambdan = krn/mun

        return lambdaw / (lambdaw + lambdan)

    # Numerical derivative
    eps = 1e-8
    dfwdx = (fw(Sw+eps) - fw(Sw-eps))/(2*eps) 
    
    return Sw, fw(Sw), dfwdx

