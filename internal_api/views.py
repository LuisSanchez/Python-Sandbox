import requests
import json
import locale
import datetime
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from webapp.models import Credit
from webapp.serializers import TMCSerializer
from external_api.views import TMCByYearAndMonth, TodayUF

_locale_decimal = locale.localeconv()['decimal_point']
_locale_thousands = locale.localeconv()['thousands_sep']

def replace_chilean_decimals(value):
    """ For some reason globalization on my computer is not working
        cant use locales, so I had to do this... terrible """
    if _locale_decimal == '.':
        value = value.replace('.', '') # replace thousands
        value = value.replace(',', '.') # sets decimals
    return float(value)

def calculate_pesos_using_uf(monto_uf, todayUF):
    """ Pesos with the UF of the day """
    pesos_amount = round(monto_uf * todayUF)
    return int(pesos_amount)

def calculate_tmc_by_given_day(credit: Credit, total_value, rate):
    """ Calcule of the tmc """
    # days to multiply the tmc (dias de mora totales)
    days_of_tmc = credit.payment_day_with_calculated_tmc - credit.payment_deadline_days
    # value of the total multiplied by the percentage of the debt rate
    total_value = round((total_value * rate) / 100)
    # amount to pay is calculated dividing the total of days of the month multiplied by the tmc days
    total_value = (total_value / 30) * days_of_tmc
    return int(total_value)

def get_type_of_tmc(monto_uf, res_tmc):
    """ Gets the tmc by current year and month, search the value by type,
        there are two types of tmc with less than 90 days,
        returns the value of tmc """
    # serializer not needed
    #tmc_serialized = TMCSerializer(res_tmc.data['TMCs'], many=True)

    # sets the type
    if monto_uf > 5000:
        tmc_type = '25'
    else:
        tmc_type = '26'

    # gets the value
    for tmc in res_tmc.data['TMCs']:
        if tmc['Tipo'] == tmc_type:
            value_tmc = tmc['Valor']
            break
    
    return value_tmc


class CalculateTMCForCredit(APIView, Credit):
    """ Calculates the tmc for the given credits on the given day after the deadline """
    def post(self, request, credit: Credit, format=None):
        dt = datetime.datetime.today()
        kwargs = { 
            'year': dt.year, 
            'month': dt.month 
        }
        # calls the external api of the bank to get the tmcs
        res_tmc = TMCByYearAndMonth.get(None, request, None, kwargs=kwargs)
        value_tmc = get_type_of_tmc(credit.monto_uf, res_tmc)

        todayUF = TodayUF.get(None, request)
        todayUF = todayUF.data['UFs'][0]["Valor"]
        valorUF = replace_chilean_decimals(todayUF)

        pesos_amount = calculate_pesos_using_uf(credit.monto_uf, valorUF)
        tmc = calculate_tmc_by_given_day(credit, pesos_amount, float(value_tmc))

        result = { 
            "total_value": pesos_amount,
            "tmc": tmc,
            "rate": value_tmc
        }
        return Response(json.dumps(result))
