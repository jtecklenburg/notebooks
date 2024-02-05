# -*- coding: utf-8 -*-
"""
Created on Tue Sep 19 17:33:53 2023

@author: jante
"""

import pdfplumber
import pandas as pd
from split_column import split_column

bigtable = list()

pdf = pdfplumber.open(r".\dehst\2022.pdf")

for page in pdf.pages:
    table = page.extract_table()
    ue1 = table.pop(0)
    ue2 = table.pop(0)

    bigtable = bigtable + table


i = 0
for col in bigtable:
    if col[3] is None:
        print("Fehler in Zeile " + str(i) + ":")
        print(col)

        print("Versuche Reperatur...")
        bigtable[i] = split_column(col[0])
        print(bigtable[i])

    i = i + 1

column_names = list()
u1_alt = ""

for [u1, u2] in zip(ue1, ue2):
    u1

    if u1 is None:
        u1 = u1_alt

    if u2 is None:
        u2 = ""

    cname = u1 + " " + u2
    cname = cname.replace("-\n", "")
    cname = cname.replace("-", "")
    cname = cname.replace("\n", " ")
    cname = cname.replace("  ", " ")
    cname = cname.replace("  ", " ")

    column_names.append(cname)

    u1_alt = u1

df = pd.DataFrame(bigtable, columns=column_names)

df.to_excel("2022.xlsx")
