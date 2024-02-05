

import re


def split_column(input_string):

# The input string and column names
# input_string = '56 14220-0019 Aktiengesellschaft der Dillinger Einheitliche Anlage Stahlwerk SL 66763 Dillingen/Saar 1.329.342 443.114 1.970.348 394.070 3.156.830 394.604 407.136 395.140 324.213 400.975 413.416 1.455.423 485.141 2.248.075 449.615 151.158 18.895 18.358 17.988 17.618 12.092 12.092 10 Herstellung von\nHüttenwerke Dillinger Hütte Roheisen und Stahl'
# column_names = ['Anlagen ID', 'Anlagen Nummer', 'Betreiber ', 'Anlagenname ', 'Bundesland ', 'PLZ ', 'Standort der Anlage ', 'Emissionen 2005 bis 2007 Gesamt in [t CO2]', 'Emissionen 2005 bis 2007 Durchschnitt/ Jahr in [t CO2]', 'Emissionen 2008 bis 2012 Gesamt in [t CO2]', 'Emissionen 2008 bis 2012 Durchschnitt/ Jahr in [t CO2]', 'Emissionen 2013 bis 2020 Gesamt in [t CO2]', 'Emissionen 2013 bis 2020 Durchschnitt/ Jahr in [t CO2]', 'Emissionen 2018 in [t CO2]', 'Emissionen 2019 in [t CO2]', 'Emissionen 2020 in [t CO2]', 'Emissionen 2021 in [t CO2]', 'Emissionen VET 2022 in [t CO2]', 'Zuteilung 2005 bis 2007 Gesamt in [EUA]', 'Zuteilung 2005 bis 2007 Durchschnitt/ Jahr in [EUA]', 'Zuteilung 2008 bis 2012 Gesamt in [EUA]', 'Zuteilung 2008 bis 2012 Durchschnitt/ Jahr in [EUA]', 'Zuteilung Zuteilung 2013 bis 2020 Gesamt in [EUA]', 'Zuteilung 2013 bis 2020 Durchschnitt/ Jahr in [EUA]', 'Zuteilung 2018 in [EUA]', 'Zuteilung 2019 in [EUA]', 'Zuteilung 2020 in [EUA]', 'Zuteilung 2021 in [EUA]', 'Zuteilung 2022 in [EUA]', 'Kleinemitten 4. HP ', 'Haupttätigkeit nach TEHG t Nr. Bezeichnung ', 'Haupttätigkeit nach TEHG t Nr. Bezeichnung Bezeichnung']

    # Create a regex pattern to match the separators (one or more spaces followed by digits)
    separator_pattern = r'\s+'

    # Split the input string using the separator pattern
    columns = re.split(separator_pattern, input_string)

    # Remove any empty strings from the list of columns
    columns = [col.strip() for col in columns if col.strip()]

    col = list()
    col.append(columns.pop(0))  # Anlagen ID
    col.append(columns.pop(0))  # Anlagen Nummer

    bundesland_pattern = r'([A-Z]{2})'

    BetreiberAnlagenname = ""

    for i in range(100):

        c = columns.pop(0)

        bundesland_match = re.search(bundesland_pattern, c)

        if bundesland_match:
            col.append(BetreiberAnlagenname[:-1])    # Betreiber + Anlagenname
            col.append("")                      # Platzhalter für Anlagenname
            col.append(c)                       # Bundesland
            break

        BetreiberAnlagenname = BetreiberAnlagenname + c + " "

        if i == 100:
            raise Exception("Ups, irgendwas ist schiefgelaufen...")

    col.append(columns.pop(0))   # PLZ

    digit_pattern = r'\d+'
    StandortDerAnlage = ""

    for i in range(100):

        c = columns.pop(0)

        digit_match = re.search(digit_pattern, c)

        if digit_match:
            col.append(StandortDerAnlage[:-1])
            col.append(c)
            break

        StandortDerAnlage = StandortDerAnlage + c

    for i in range(22):
        col.append(columns.pop(0))

    Haupttaetigkeit = ""

    for c in columns:
        Haupttaetigkeit = Haupttaetigkeit + c + " "

    col.append(Haupttaetigkeit[:-1])    # Haupttätigkeit 1 + 2
    col.append("")                      # Platzhalter für Haupttätigkeit 2

    return col
