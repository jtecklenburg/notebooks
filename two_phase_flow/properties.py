import pandas as pd
import matplotlib.pyplot as plt
from scipy.interpolate import LinearNDInterpolator
from numpy import array

def from_table(column="Density (kg/m3)", path2excel="Properties_CO2.xlsx", sheet_name="table2", plot=True):
    """
    Reads an Excel-File with thermophysical data and returns a function rho(p, T)

    Parameters
    ----------
    path2excel : str
        path to Excel file with thermophysical data of carbon dioxide
    sheet_name : str
        sheet_name in Excel file
    plot : bool, optional
        plot data in Excel file?
        The default is True.

    Returns
    -------
    interpolator : float value = f(p, T)
        value as function of pressure p (MPa) and temperature T (°C)

    """

    df = pd.read_excel(path2excel, sheet_name=sheet_name)

    # pick columns
    T = df["Temperature (C)"]
    p = df["Pressure (MPa)"]
    value = df[column]

    interpolator = LinearNDInterpolator(array([p, T]).T, value)

    if plot:
        fig = plt.figure()
        ax = fig.add_subplot(projection='3d')
        ax.scatter(T, p, value, marker='o')
        ax.set_xlabel("Temperature T (°C)")
        ax.set_ylabel("Pressure p (MPa)")
        ax.set_zlabel(column)

    return interpolator