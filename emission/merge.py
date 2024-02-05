# -*- coding: utf-8 -*-
"""
Created on Tue Sep 26 11:29:10 2023

@author: jante
"""
import pandas as pd
import geopandas as gpd

data = pd.read_excel("2022.xlsx")
plz = gpd.read_file(r".\plz-2stellig\plz-2stellig.shp")
data_2021 = data[["PLZ ", "Emissionen 2021 in [t CO2]"]].copy()


data_2021["Emissionen 2021 in [t CO2]"] = data_2021["Emissionen 2021 in [t CO2]"].map(lambda x: x.replace(".", ""))

data_2021["Emissionen 2021 in [t CO2]"] = pd.to_numeric(data_2021["Emissionen 2021 in [t CO2]"], errors="coerce")



PLZ_5 = [('0' + str(b)) if (b < 10000) else str(b) for b in data_2021['PLZ ']]
PLZ_2 = [i[:2] for i in PLZ_5]
data_2021["PLZ_2"] = PLZ_2

data_2021 = data_2021.groupby(['PLZ_2'])["Emissionen 2021 in [t CO2]"].sum().reset_index()



plz = pd.merge(plz, data_2021, left_on='plz', right_on='PLZ_2', how='left')

# No data in table for plz area 61
plz["Emissionen 2021 in [t CO2]"] = plz["Emissionen 2021 in [t CO2]"].fillna(0)


# plz.plot(column="Emissionen 2021 in [t CO2]", cmap='plasma', legend=True)


# https://gas.info/carbon-management/co2-netz


col = ['Emissionen 2005 bis 2007 Durchschnitt/ Jahr in [t CO2]',
       'Emissionen 2008 bis 2012 Durchschnitt/ Jahr in [t CO2]',
       'Emissionen 2013 bis 2020 Durchschnitt/ Jahr in [t CO2]',
       'Emissionen 2018 in [t CO2]', 'Emissionen 2019 in [t CO2]',
       'Emissionen 2020 in [t CO2]', 'Emissionen 2021 in [t CO2]']


years = [2006, 2010, 2016, 2018, 2019, 2020, 2021]

for c in col:
    data[c] = data[c].map(lambda x: x.replace(".", ""))
    data[c] = pd.to_numeric(data[c], errors="coerce")


total_emission = data[col].sum()

import matplotlib.pyplot as plt

plt.figure()
plt.plot(years, total_emission, 'o-')
plt.show()



emissions_sector = data.groupby(['Haupttätigkeit nach TEHG t Nr. Bezeichnung '])[col].sum().reset_index()


plt.figure()
plt.plot(years, emissions_sector[col].values.transpose(), 'o-')
#plt.legend(emissions_sector['Haupttätigkeit nach TEHG t Nr. Bezeichnung '])
plt.show()

plt.figure()
plt.plot(years, emissions_sector[emissions_sector['Haupttätigkeit nach TEHG t Nr. Bezeichnung '] != 2][col].values.transpose(), 'o-')
plt.show()


plt.figure()
plt.plot(years, data[data['Haupttätigkeit nach TEHG t Nr. Bezeichnung '] == 2][col].values.transpose(), 'o-')
plt.show()


top5_kraftwerke = data[data['Haupttätigkeit nach TEHG t Nr. Bezeichnung '] == 2].sort_values(by=['Emissionen 2005 bis 2007 Durchschnitt/ Jahr in [t CO2]'], ascending=False).head(5)

print(top5_kraftwerke[['Betreiber ', 'Anlagenname ', 'Bundesland ']])


betreiber = data.groupby(['Betreiber '])[col].sum().reset_index()

top5_betreiber_2006 = betreiber.sort_values(by=['Emissionen 2005 bis 2007 Durchschnitt/ Jahr in [t CO2]'], ascending=False).head(10)
print(top5_betreiber_2006[['Betreiber ', 'Emissionen 2005 bis 2007 Durchschnitt/ Jahr in [t CO2]']])


top5_betreiber_2021 = betreiber.sort_values(by=['Emissionen 2021 in [t CO2]'], ascending=False).head(10)
print(top5_betreiber_2021[['Betreiber ', 'Emissionen 2021 in [t CO2]']])
